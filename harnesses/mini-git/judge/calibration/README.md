# LLM Judge Calibration

This directory contains reference implementations with human expert scores,
used to calibrate the LLM judge so that scores are consistent across models
and across time.

## Purpose

Calibration ensures that when three different LLM judges score the same
implementation, they converge on similar scores. Without calibration, judge
scores drift based on each model's priors about what "good code" looks like.

## How Calibration Works

1. A human expert reads `judge/rubric.md` and scores a reference implementation
2. The expert writes their reasoning for each dimension
3. These become the "ground truth" scores in `scores.json`
4. Before each judge run, the judge model is shown these calibration examples
   and asked to score them first — then its scores are anchored against the
   ground truth (if drift > 15 points on any dimension, the judge is re-prompted)

## Directory Structure

```
calibration/
  README.md              ← This file
  scores.json            ← Ground truth scores for all samples
  sample_good/           ← Example of a high-quality mini-git implementation
    notes.md             ← What makes this good
    code_excerpt.py      ← Representative code excerpts
  sample_bad/            ← Example of a low-quality implementation
    notes.md
    code_excerpt.py
```

## Adding New Calibration Samples

1. Create a new `sample_<label>/` directory
2. Add `notes.md` and representative `code_excerpt.py`
3. Have at least two human experts independently score it using `judge/rubric.md`
4. Average the scores and add to `scores.json` with `human_scores` and inter-rater agreement
5. Mark samples with agreement < 10 points as "calibrated"; others as "disputed"

## Notes

- Keep calibration samples under 200 lines of code excerpts
- Refresh calibration samples when harness version increments
- The calibration set is NOT used for training — it's only shown at inference time
