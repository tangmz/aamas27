# Blue Sky working draft

`main.tex` is the editable anonymous manuscript; `references.bib` contains the source list. `main.pdf`, when built, is for author/supervisor review. The submission ID is deliberately DRAFT. The source follows the official AAMAS 2027 template, retrieved on 3 October 2026 from https://warwick.ac.uk/fac/sci/dcs/aamas2027/aamas_2027_template.zip . The bundled class and bibliography style are unmodified.

The draft is a proposed research agenda, not an accepted paper or a demonstrated effectiveness result. Consult `../../docs/recovery-plan.md` for deadlines, remaining evidence and execution instructions, and `../../docs/novelty-review.md` for the scoped literature comparison.

`submission-materials.md` contains the abstract, Blue Sky rationale and a **chair-only identifying author-background draft**. `ai-assistance-disclosure.md` is an incomplete provenance record requiring author verification and anonymization. Do not upload either file unchanged as anonymous supplementary material. Keep credentials and identifying filesystem paths out of a release.

Compile in this directory with a LaTeX installation:

```powershell
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Or use Tectonic (`tectonic main.tex`). The portable compiler downloaded for local verification is under `runs/tools/tectonic`; it is ignored by Git.

Before submission: supervisor review, a completed institutional-dialogue literature comparison, verified tool/model provenance, final four-page body check, actual submission ID, author approvals, and the required OpenReview fields are still necessary. No external submission has been performed.
