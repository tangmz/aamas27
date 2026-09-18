"""Execute the reporting notebook using the local research kernel; no model calls."""
import argparse
import os
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=root/'runs/study-verified')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    run=args.run.resolve()
    os.environ['DISSENT_STUDY_DIR']=str(run)
    for name,directory in [('JUPYTER_RUNTIME_DIR',root/'.venv/jupyter-runtime'),('IPYTHONDIR',root/'.venv/ipython'),('MPLCONFIGDIR',root/'.venv/matplotlib')]:
        directory.mkdir(parents=True,exist_ok=True)
        os.environ[name]=str(directory)
    import nbformat
    from nbclient import NotebookClient
    notebook=nbformat.read(root/'notebooks/research_report.ipynb',as_version=4)
    client=NotebookClient(notebook,timeout=180,kernel_name='dissent-research',resources={'metadata':{'path':str(root)}})
    client.execute()
    output=args.out or run/'research_report.executed.ipynb'
    output.parent.mkdir(parents=True,exist_ok=True)
    nbformat.write(notebook,output)
    print('Executed all notebook cells:',output)


if __name__=='__main__': main()
