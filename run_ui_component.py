#!/usr/bin/env python3
"""
Additional experiment: UI component color recognition
Tests VLMs on realistic UI components (button, card, badge) instead of solid fills.
"""

import os, sys, json, time, base64, math, requests, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

EXPERIMENT_DIR = Path(__file__).parent
RESULTS_DIR = EXPERIMENT_DIR / "results"
UI_IMAGES_DIR = EXPERIMENT_DIR / "images" / "ui_components"
UI_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

TRIALS = 3

PROMPT = "This UI component has a colored element. What is the exact HEX color code of the main colored area (button/card/badge background)? Reply ONLY with #XXXXXX format."

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

def parse_hex(text):
    m = re.search(r'#([0-9A-Fa-f]{6})', text)
    return f"#{m.group(1).upper()}" if m else None

# UI Component generators
def get_font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try: return ImageFont.truetype(p, size)
        except: pass
    return ImageFont.load_default()

def generate_button(color_hex, path):
    """Generate a button UI component on white background"""
    img = Image.new('RGB', (400, 200), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    rgb = hex_to_rgb(color_hex)
    # Rounded button
    draw.rounded_rectangle([(50, 60), (350, 140)], radius=12, fill=rgb)
    draw.text((130, 85), "Submit", fill=(255, 255, 255), font=get_font(24))
    img.save(str(path))

def generate_card(color_hex, path):
    """Generate a card header UI component"""
    img = Image.new('RGB', (400, 300), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    rgb = hex_to_rgb(color_hex)
    # Card with colored header
    draw.rounded_rectangle([(20, 20), (380, 280)], radius=12, fill=(255, 255, 255), outline=(220, 220, 220))
    draw.rounded_rectangle([(20, 20), (380, 100)], radius=12, fill=rgb)
    draw.rectangle([(20, 80), (380, 100)], fill=rgb)  # fix bottom corners
    draw.text((40, 45), "Dashboard", fill=(255, 255, 255), font=get_font(22))
    draw.text((40, 120), "Total users: 1,234", fill=(100, 100, 100), font=get_font(16))
    draw.text((40, 150), "Revenue: $56,789", fill=(100, 100, 100), font=get_font(16))
    img.save(str(path))

def generate_badge(color_hex, path):
    """Generate a badge/tag UI component"""
    img = Image.new('RGB', (300, 150), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    rgb = hex_to_rgb(color_hex)
    draw.rounded_rectangle([(80, 45), (220, 105)], radius=20, fill=rgb)
    draw.text((100, 60), "Active", fill=(255, 255, 255), font=get_font(20))
    img.save(str(path))

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

if __name__ == "__main__":
    # Load env
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

    # 6 representative colors × 3 component types = 18 stimuli
    test_colors = [
        ("#FF0000", "red"),      # primary
        ("#00FF00", "green"),    # primary
        ("#0000FF", "blue"),     # primary
        ("#00BF7F", "teal"),     # intermediate (problematic)
        ("#7F00FF", "purple"),   # intermediate (problematic)
        ("#FF7F00", "orange"),   # intermediate
    ]
    
    component_generators = {
        "button": generate_button,
        "card": generate_card,
        "badge": generate_badge,
    }
    
    models = {"gpt-4o": call_openai, "claude-sonnet-4": call_claude}
    results = []
    
    for color_hex, color_name in test_colors:
        for comp_name, gen_fn in component_generators.items():
            img_path = UI_IMAGES_DIR / f"{color_name}_{comp_name}.png"
            gen_fn(color_hex, img_path)
            
            with open(img_path, 'rb') as f:
                img_b64 = base64.b64encode(f.read()).decode()
            
            for model_name, model_fn in models.items():
                for trial in range(TRIALS):
                    try:
                        response, _ = model_fn(img_b64, PROMPT)
                        resp_hex = parse_hex(response)
                        de = None
                        if resp_hex:
                            lab1 = rgb_to_lab(*hex_to_rgb(color_hex))
                            lab2 = rgb_to_lab(*hex_to_rgb(resp_hex))
                            de = ciede2000(lab1, lab2)
                        results.append({
                            "color": color_hex, "color_name": color_name,
                            "component": comp_name, "model": model_name,
                            "trial": trial + 1, "response": response,
                            "response_hex": resp_hex, "delta_e_2000": de
                        })
                        print(f"  {model_name} {color_name} {comp_name} t{trial+1}: {resp_hex} ΔE={de:.2f}" if de else f"  {model_name} {color_name} {comp_name} t{trial+1}: PARSE FAIL")
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"  ERROR: {e}")
                        results.append({
                            "color": color_hex, "color_name": color_name,
                            "component": comp_name, "model": model_name,
                            "trial": trial + 1, "error": str(e)
                        })
    
    with open(RESULTS_DIR / "ui_component_results.json", 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Summary
    for model_name in models:
        solid_placeholder = []  # compare with solid later
        for comp_name in component_generators:
            vals = [r['delta_e_2000'] for r in results if r.get('model') == model_name and r.get('component') == comp_name and r.get('delta_e_2000') is not None]
            if vals:
                print(f"\n{model_name} {comp_name}: mean ΔE={sum(vals)/len(vals):.2f}, n={len(vals)}")
    
    print("\n✅ UI component experiment complete")
