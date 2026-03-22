#!/usr/bin/env python3
"""
Additional experiment: English prompt comparison
Tests a subset (12 high-saturation colors) with English prompt to assess language dependency.
"""

import os, sys, json, time, base64, colorsys, math, requests
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).parent
RESULTS_DIR = EXPERIMENT_DIR / "results"
IMAGES_DIR = EXPERIMENT_DIR / "images"

PROMPT_EN = "This image is filled with a single solid color. Please tell me the exact HEX color code. Reply ONLY with #XXXXXX format. No explanation needed."
PROMPT_JA = "この画像は単一色で塗りつぶされています。その色のHEXコードを正確に答えてください。#XXXXXXの形式のみで回答してください。説明は不要です。"
TRIALS = 3

def call_openai(image_b64, prompt):
    api_key = os.environ.get('OPENAI_API_KEY')
    resp = requests.post("https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
        ]}], "max_tokens": 50},
        timeout=30
    )
    data = resp.json()
    return data['choices'][0]['message']['content'].strip(), None

def call_claude(image_b64, prompt):
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    resp = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": "claude-sonnet-4-20250514", "max_tokens": 50, "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
            {"type": "text", "text": prompt}
        ]}]},
        timeout=30
    )
    data = resp.json()
    return data['content'][0]['text'].strip(), None

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_lab(r, g, b):
    def linearize(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    rl, gl, bl = linearize(r), linearize(g), linearize(b)
    x = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375
    y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041
    xn, yn, zn = 0.95047, 1.0, 1.08883
    def f(t): return t ** (1/3) if t > 0.008856 else (7.787 * t + 16/116)
    fx, fy, fz = f(x/xn), f(y/yn), f(z/zn)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)

def ciede2000(lab1, lab2):
    L1, a1, b1 = lab1; L2, a2, b2 = lab2
    C1 = math.sqrt(a1**2 + b1**2); C2 = math.sqrt(a2**2 + b2**2)
    C_avg = (C1 + C2) / 2; C_avg7 = C_avg**7
    G = 0.5 * (1 - math.sqrt(C_avg7 / (C_avg7 + 25**7)))
    a1p = a1 * (1 + G); a2p = a2 * (1 + G)
    C1p = math.sqrt(a1p**2 + b1**2); C2p = math.sqrt(a2p**2 + b2**2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp = L2 - L1; dCp = C2p - C1p
    if C1p * C2p == 0: dhp = 0
    elif abs(h2p - h1p) <= 180: dhp = h2p - h1p
    elif h2p - h1p > 180: dhp = h2p - h1p - 360
    else: dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lp_avg = (L1 + L2) / 2; Cp_avg = (C1p + C2p) / 2
    if C1p * C2p == 0: hp_avg = h1p + h2p
    elif abs(h1p - h2p) <= 180: hp_avg = (h1p + h2p) / 2
    elif h1p + h2p < 360: hp_avg = (h1p + h2p + 360) / 2
    else: hp_avg = (h1p + h2p - 360) / 2
    T = (1 - 0.17*math.cos(math.radians(hp_avg-30)) + 0.24*math.cos(math.radians(2*hp_avg))
         + 0.32*math.cos(math.radians(3*hp_avg+6)) - 0.20*math.cos(math.radians(4*hp_avg-63)))
    SL = 1 + 0.015*(Lp_avg-50)**2/math.sqrt(20+(Lp_avg-50)**2)
    SC = 1 + 0.045*Cp_avg; SH = 1 + 0.015*Cp_avg*T
    Cp_avg7 = Cp_avg**7
    RT = -2*math.sqrt(Cp_avg7/(Cp_avg7+25**7))*math.sin(math.radians(60*math.exp(-((hp_avg-275)/25)**2)))
    return math.sqrt((dLp/SL)**2 + (dCp/SC)**2 + (dHp/SH)**2 + RT*(dCp/SC)*(dHp/SH))

import re
def parse_hex(text):
    m = re.search(r'#([0-9A-Fa-f]{6})', text)
    return f"#{m.group(1).upper()}" if m else None

if __name__ == "__main__":
    # Load env
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()
    
    # Test 12 high-saturation colors only
    hues = list(range(0, 360, 30))
    results = {"gpt-4o": [], "claude-sonnet-4": []}
    
    models = {
        "gpt-4o": call_openai,
        "claude-sonnet-4": call_claude,
    }
    
    for hue in hues:
        r, g, b = colorsys.hls_to_rgb(hue / 360.0, 0.5, 1.0)
        hex_code = f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"
        img_path = IMAGES_DIR / f"h{hue}_high.png"
        
        if not img_path.exists():
            from PIL import Image
            img = Image.new('RGB', (200, 200), hex_to_rgb(hex_code))
            img.save(str(img_path))
        
        with open(img_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode()
        
        for model_name, model_fn in models.items():
            for prompt_name, prompt in [("english", PROMPT_EN), ("japanese", PROMPT_JA)]:
                for trial in range(TRIALS):
                    try:
                        response, _ = model_fn(img_b64, prompt)
                        resp_hex = parse_hex(response)
                        de = None
                        if resp_hex:
                            lab1 = rgb_to_lab(*hex_to_rgb(hex_code))
                            lab2 = rgb_to_lab(*hex_to_rgb(resp_hex))
                            de = ciede2000(lab1, lab2)
                        results[model_name].append({
                            "hue": hue, "ground_truth": hex_code,
                            "prompt_lang": prompt_name, "trial": trial + 1,
                            "response": response, "response_hex": resp_hex,
                            "delta_e_2000": de
                        })
                        print(f"  {model_name} {prompt_name} hue={hue} trial={trial+1}: {resp_hex} ΔE={de:.2f}" if de else f"  {model_name} {prompt_name} hue={hue} trial={trial+1}: PARSE FAIL")
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"  ERROR: {model_name} {prompt_name} hue={hue}: {e}")
                        results[model_name].append({
                            "hue": hue, "ground_truth": hex_code,
                            "prompt_lang": prompt_name, "trial": trial + 1,
                            "error": str(e)
                        })
    
    # Save
    with open(RESULTS_DIR / "english_prompt_comparison.json", 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Summary
    for model_name in models:
        for lang in ["english", "japanese"]:
            vals = [r['delta_e_2000'] for r in results[model_name] if r.get('prompt_lang') == lang and r.get('delta_e_2000') is not None]
            if vals:
                print(f"\n{model_name} ({lang}): mean ΔE={sum(vals)/len(vals):.2f}, n={len(vals)}")
    
    print("\n✅ English prompt comparison complete")
