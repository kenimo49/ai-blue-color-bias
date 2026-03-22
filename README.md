# AI Blue: Systematic Color Recognition Bias in Vision-Language Models

> **Paper**: *AI Blue: Systematic Color Recognition Bias in Vision-Language Models and Its Implications for AI-Generated UI Design*
>
> **Author**: Ken Imoto (Propel-Lab) — [kenimoto.dev](https://kenimoto.dev)

## Overview

This repository contains the code, data, and paper for a systematic evaluation of color recognition accuracy across four Vision-Language Models (VLMs):

- **GPT-4o** (OpenAI)
- **Claude 3.5 Sonnet** (Anthropic)
- **Claude Sonnet 4** (Anthropic)
- **LLaVA 7B** (Open-source)

We tested 40 colors × 4 models × 3 trials = **480 observations**, measured by **CIEDE2000** color difference.

## Key Findings

| Model | Mean ΔE₀₀ | Parse Rate |
|-------|-----------|------------|
| GPT-4o | **2.51** | 100% |
| Claude 3.5 Sonnet | 3.16 | 100% |
| Claude Sonnet 4 | 3.33 | 100% |
| LLaVA 7B | 24.63 | 78% |

- Commercial VLMs achieve moderate accuracy (ΔE₀₀ 2.5–3.3) but systematically fail on intermediate hues
- LLaVA 7B shows substantially lower accuracy (p < 0.001, Cohen's d = −1.75)
- Claude Sonnet 4 performs **worse** than Claude 3.5 Sonnet (model version regression)
- Prompt language (English vs Japanese) has minimal effect on accuracy
- AI-generated UIs are 95.4% concentrated in the blue-purple (240°) hue range

## Repository Structure

```
├── run_experiment.py          # Main experiment (40 colors × 4 models × 3 trials)
├── run_english_prompt.py      # Cross-lingual prompt comparison
├── run_ui_component.py        # UI component context experiment
├── images/                    # Stimulus images (solid colors)
│   └── ui_components/         # Button, card, badge images
├── results/                   # Raw JSON results
│   ├── gpt-4o.json
│   ├── claude-3.5-sonnet.json
│   ├── claude-sonnet-4.json
│   ├── llava-7b.json
│   ├── english_prompt_comparison.json
│   ├── ui_component_results.json
│   ├── statistics.json
│   └── color_distribution_analysis.json
└── paper/
    ├── main.tex               # LaTeX source
    ├── main.pdf               # Compiled paper
    └── figures/               # Generated figures
```

## Reproducing the Experiments

### Requirements

```bash
pip install Pillow requests
```

### Running

Set your API keys as environment variables (or create a `.env` file):

```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
```

```bash
# Main experiment
python run_experiment.py

# English vs Japanese prompt comparison
python run_english_prompt.py

# UI component experiment
python run_ui_component.py
```

### Compiling the Paper

```bash
cd paper
pdflatex main.tex
pdflatex main.tex  # Run twice for references
```

## Citation

If you use this work, please cite:

```bibtex
@article{imoto2026aiblue,
  title={AI Blue: Systematic Color Recognition Bias in Vision-Language Models and Its Implications for AI-Generated UI Design},
  author={Imoto, Ken},
  year={2026},
  note={Preprint}
}
```

## License

MIT License
