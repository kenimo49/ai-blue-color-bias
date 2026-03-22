#!/usr/bin/env python3
"""
008: AI Blue — Vision-Language Model Color Recognition Bias Experiment
Generates solid-color images, sends to VLMs, collects HEX responses, calculates ΔE.
"""

import os
import sys
import json
import time
import base64
import colorsys
import math
import requests
from pathlib import Path
from datetime import datetime

# --- Config ---
EXPERIMENT_DIR = Path(__file__).parent
RESULTS_DIR = EXPERIMENT_DIR / "results"
IMAGES_DIR = EXPERIMENT_DIR / "images"
RESULTS_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

TRIALS = 3  # trials per color per model
PROMPT = "この画像は単一色で塗りつぶされています。その色のHEXコードを正確に答えてください。#XXXXXXの形式のみで回答してください。説明は不要です。"

# --- Color Set Generation ---
def generate_color_set():
    """Generate 40 test colors: 12 hues × 3 saturations + 4 achromatic"""
    colors = []
    
    # Chromatic colors: 12 hues × 3 (high/mid/low saturation)
    hues = list(range(0, 360, 30))  # 0, 30, 60, ..., 330
    sat_levels = [
        ("high", 1.0, 0.5),   # full saturation, medium lightness
        ("mid",  0.6, 0.5),   # medium saturation
        ("low",  0.3, 0.6),   # low saturation, slightly lighter (pastel)
    ]
    
    for hue in hues:
        for sat_name, sat, light in sat_levels:
            r, g, b = colorsys.hls_to_rgb(hue / 360.0, light, sat)
            hex_code = f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"
            colors.append({
                "hex": hex_code,
                "hue": hue,
                "saturation": sat,
                "lightness": light,
                "category": f"h{hue}_{sat_name}",
                "label": f"Hue {hue}° {sat_name} sat"
            })
    
    # Achromatic colors
    for val, name in [(0, "black"), (85, "dark_gray"), (170, "light_gray"), (255, "white")]:
        hex_code = f"#{val:02X}{val:02X}{val:02X}"
        colors.append({
            "hex": hex_code,
            "hue": None,
            "saturation": 0,
            "lightness": val / 255.0,
            "category": name,
            "label": name
        })
    
    return colors


def generate_color_image(hex_code, filepath, size=200):
    """Generate a solid color PNG image using Pillow"""
    from PIL import Image
    r = int(hex_code[1:3], 16)
    g = int(hex_code[3:5], 16)
    b = int(hex_code[5:7], 16)
    img = Image.new('RGB', (size, size), (r, g, b))
    img.save(filepath, 'PNG')


def image_to_base64(filepath):
    with open(filepath, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


# --- Model Calls ---
def call_gpt4o(image_b64, prompt):
    """Call GPT-4o vision API"""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None, "API key not set"
    
    resp = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={
            'model': 'gpt-4o',
            'max_tokens': 50,
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{image_b64}'}}
                ]
            }]
        },
        timeout=30
    )
    
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
    
    data = resp.json()
    text = data['choices'][0]['message']['content'].strip()
    return text, None


def call_claude(image_b64, prompt):
    """Call Claude 3.5 Sonnet vision API"""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None, "API key not set"
    
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        },
        json={
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 50,
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': image_b64}},
                    {'type': 'text', 'text': prompt}
                ]
            }]
        },
        timeout=30
    )
    
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
    
    data = resp.json()
    text = data['content'][0]['text'].strip()
    return text, None


def call_llava(image_b64, prompt):
    """Call LLaVA via ollama on autocrew-wsl (SSH tunnel or direct API)"""
    # Try direct ollama API via SSH port forward or local
    ollama_host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
    
    try:
        resp = requests.post(
            f'{ollama_host}/api/generate',
            json={
                'model': 'llava:7b',
                'prompt': prompt,
                'images': [image_b64],
                'stream': False,
                'options': {'num_predict': 50}
            },
            timeout=120
        )
        
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        text = data.get('response', '').strip()
        return text, None
    except Exception as e:
        return None, str(e)


# --- Color Analysis ---
def hex_to_rgb(hex_code):
    hex_code = hex_code.lstrip('#')
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_lab(r, g, b):
    """Convert RGB to CIELAB (simplified)"""
    # Normalize to 0-1
    r, g, b = r/255.0, g/255.0, b/255.0
    
    # Linearize (sRGB gamma)
    def linearize(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    
    r, g, b = linearize(r), linearize(g), linearize(b)
    
    # RGB to XYZ (D65)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    
    # XYZ to Lab
    xn, yn, zn = 0.95047, 1.00000, 1.08883
    
    def f(t):
        return t ** (1/3) if t > 0.008856 else (7.787 * t) + (16/116)
    
    L = 116 * f(y/yn) - 16
    a = 500 * (f(x/xn) - f(y/yn))
    b_val = 200 * (f(y/yn) - f(z/zn))
    
    return L, a, b_val


def delta_e_cie2000(lab1, lab2):
    """Calculate CIEDE2000 color difference (simplified implementation)"""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    
    # Simple Euclidean ΔE*ab for now (ΔE76)
    # TODO: Implement full CIEDE2000 for paper
    dL = L2 - L1
    da = a2 - a1
    db = b2 - b1
    
    return math.sqrt(dL**2 + da**2 + db**2)


def rgb_to_hsl(r, g, b):
    """Convert RGB (0-255) to HSL"""
    h, l, s = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
    return h * 360, s, l


def parse_hex_from_response(response_text):
    """Extract HEX code from model response"""
    import re
    if not response_text:
        return None
    match = re.search(r'#([0-9A-Fa-f]{6})', response_text)
    return f"#{match.group(1).upper()}" if match else None


# --- Main Experiment ---
def run_experiment():
    print("=" * 60)
    print("008: AI Blue — Color Recognition Bias Experiment")
    print("=" * 60)
    
    colors = generate_color_set()
    print(f"\n📊 Test colors: {len(colors)}")
    
    # Generate images
    print("\n🎨 Generating color images...")
    for color in colors:
        img_path = IMAGES_DIR / f"{color['category']}.png"
        generate_color_image(color['hex'], img_path)
    print(f"   Generated {len(colors)} images")
    
    # Define models
    models = {
        'gpt-4o': call_gpt4o,
        'claude-3.5-sonnet': call_claude,
        # 'llava-7b': call_llava,  # Enable when ready
    }
    
    # Check llava availability
    try:
        ollama_host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
        r = requests.get(f'{ollama_host}/api/tags', timeout=5)
        if r.status_code == 200:
            available = [m['name'] for m in r.json().get('models', [])]
            if any('llava' in m for m in available):
                models['llava-7b'] = call_llava
                print("✅ LLaVA 7B available via ollama")
    except:
        print("⚠️ LLaVA not available (ollama unreachable)")
    
    print(f"\n🤖 Models: {', '.join(models.keys())}")
    print(f"🔄 Trials per color: {TRIALS}")
    print(f"📈 Total API calls: {len(colors) * len(models) * TRIALS}")
    
    all_results = []
    
    for model_name, model_fn in models.items():
        print(f"\n{'='*40}")
        print(f"Running: {model_name}")
        print(f"{'='*40}")
        
        model_results = []
        
        for i, color in enumerate(colors):
            img_path = IMAGES_DIR / f"{color['category']}.png"
            img_b64 = image_to_base64(img_path)
            
            for trial in range(TRIALS):
                print(f"  [{i+1}/{len(colors)}] {color['label']} trial {trial+1}... ", end="", flush=True)
                
                response, error = model_fn(img_b64, PROMPT)
                
                if error:
                    print(f"❌ {error[:50]}")
                    result = {
                        "model": model_name,
                        "color": color,
                        "trial": trial + 1,
                        "response_raw": None,
                        "response_hex": None,
                        "error": error,
                        "delta_e": None,
                        "hue_shift": None,
                    }
                else:
                    parsed_hex = parse_hex_from_response(response)
                    
                    if parsed_hex:
                        actual_rgb = hex_to_rgb(color['hex'])
                        response_rgb = hex_to_rgb(parsed_hex)
                        
                        actual_lab = rgb_to_lab(*actual_rgb)
                        response_lab = rgb_to_lab(*response_rgb)
                        de = delta_e_cie2000(actual_lab, response_lab)
                        
                        # Hue shift
                        if color['hue'] is not None:
                            resp_hsl = rgb_to_hsl(*response_rgb)
                            hue_shift = resp_hsl[0] - color['hue']
                            if hue_shift > 180: hue_shift -= 360
                            if hue_shift < -180: hue_shift += 360
                        else:
                            hue_shift = None
                        
                        print(f"✅ {parsed_hex} (ΔE={de:.1f}, shift={hue_shift:+.0f}°)" if hue_shift is not None else f"✅ {parsed_hex} (ΔE={de:.1f})")
                    else:
                        de = None
                        hue_shift = None
                        print(f"⚠️ Could not parse: {response[:50]}")
                    
                    result = {
                        "model": model_name,
                        "color": color,
                        "trial": trial + 1,
                        "response_raw": response,
                        "response_hex": parsed_hex,
                        "error": None,
                        "delta_e": de,
                        "hue_shift": hue_shift,
                    }
                
                model_results.append(result)
                all_results.append(result)
                
                # Rate limit
                time.sleep(1)
        
        # Save per-model results
        with open(RESULTS_DIR / f"{model_name}.json", 'w') as f:
            json.dump(model_results, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 Saved {len(model_results)} results to {model_name}.json")
    
    # Save combined results
    with open(RESULTS_DIR / "all_results.json", 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    
    # Quick summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for model_name in models:
        model_data = [r for r in all_results if r['model'] == model_name and r['delta_e'] is not None]
        if model_data:
            des = [r['delta_e'] for r in model_data]
            shifts = [r['hue_shift'] for r in model_data if r['hue_shift'] is not None]
            
            print(f"\n{model_name}:")
            print(f"  Mean ΔE: {sum(des)/len(des):.2f}")
            print(f"  Max ΔE:  {max(des):.2f}")
            print(f"  Min ΔE:  {min(des):.2f}")
            if shifts:
                print(f"  Mean Hue Shift: {sum(shifts)/len(shifts):+.1f}°")
                blue_shifts = [s for s in shifts if s > 0]  # positive = toward blue
                print(f"  Blue-ward shifts: {len(blue_shifts)}/{len(shifts)} ({100*len(blue_shifts)/len(shifts):.0f}%)")
    
    print(f"\n✅ Experiment complete. Results in {RESULTS_DIR}/")
    return all_results


if __name__ == '__main__':
    run_experiment()
