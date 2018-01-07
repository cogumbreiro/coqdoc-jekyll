from bs4 import BeautifulSoup
import re
import shlex
import os.path
import subprocess

def fix_title(elem, h):
    hdr = elem.find(h, 'section')
    if hdr is not None:
        lbl = hdr.find_previous_sibling('a').extract()
        hdr = hdr.extract()
        elem.insert_before(hdr)
        hdr.wrap(lbl)


def fix_tufte(fdin):
    """
    The actual code that cleans up the HTML files according to what
    Tufte CSS expects.
    """
    data = fdin.read()
    data = re.sub(r'(<br/>\n*)+', r'<br/>', data, flags=re.MULTILINE)
    data = re.sub(r'<div class="paragraph"> </div>', '', data)
    data = re.sub(r'(<br/>\n)+<\div>', r'<\div>', data, flags=re.MULTILINE)
    data = re.sub(r'<div class="code">\n+<br/>', '<div class="code">', data, flags=re.MULTILINE)
    data = re.sub(r'<div class="code">\n+(<br\/>)?', '<div class="code">', data, flags=re.MULTILINE)
    data = re.sub(r'<div class="code"></div>', '', data)
    bs = BeautifulSoup(data, 'html.parser')
    page = bs.find('div', id='page')
    if page is not None:
        page.name = 'article'
        del page['id']
        del page['class']
    
    main = bs.find('div', id='main')
    if main is not None:
        main.name = 'section'
        del main['id']

    for elem in bs.find_all('div', 'doc'):
        for h in ('h1', 'h2', 'h3'):
            fix_title(elem, h)

        elem.name = 'p'
        del elem['class']

    for elem in bs.find_all('div', 'code'):
        elem.name = 'pre'
        del elem['class']

    mark = bs.find(text=re.compile('^This page has been generated'))
    if mark is not None:
        mark.find_previous_sibling('hr').decompose()
        mark.find_next_sibling('a').decompose()
        mark.replace_with('')

    for elem in bs.find_all('div'):
        if elem.text.strip() == "":
            elem.decompose()

    return bs

def fix(filename):
    """
    Massages the HTML to what Tufte CSS expects.
    """
    with open(filename) as fp:
        bs = fix_tufte(fp)
    with open(filename, "w") as fp:
        fp.write("""---
layout: default
---
""")
        fp.write(str(bs.prettify()))

class Project:
    """
    Parses a Coq Project file.
    """
    def __init__(self, args, coq_files):
        self.args = args
        self.coq_files = coq_files
        self.base_dir = None
        self.base_package = None
        if args[0] == "-R" or args[0] == "-Q":
            self.base_dir = args[1]
            self.base_package = args[2]

    @property
    def html_files(self):
        return list(self._as_html(x) for x in self.coq_files)

    def _as_html(self, fname):
        if self.base_dir is not None and fname.startswith(self.base_dir):
            fname = fname[len(self.base_dir):]
        if fname.startswith(os.path.sep):
            fname = fname[1:]
        fname = fname.replace(os.path.sep, '.')
        if self.base_package is not None:
            fname = self.base_package + "." + fname
        fname = os.path.splitext(fname)[0]
        return fname + ".html"

    @classmethod
    def load(cls, filename):
        """
        Opens a `_CoqProject` file and parses it.
        """
        with open(filename) as fp:
            lines = list(fp)
        
        return cls(
            args = shlex.split(lines[0]),
            coq_files = list(x.strip() for x in lines[1:] if x.strip() != "" and not x.strip().startswith("#")),
        )

DEFAULT_ARGS = "--body-only --no-index --lib-subtitles -s -g -l"

def main():
    import sys, argparse
    parser = argparse.ArgumentParser(description='coqdoc using Tufte CSS.')
    d_target_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    parser.add_argument("-d", default=d_target_dir, dest="target_dir", help="Target directory. Default: %(default)s")
    parser.add_argument("-p", default="_CoqProject", dest="project_file", help="Coq Project file. Default: %(default)s")
    args = parser.parse_args()

    prj = Project.load(args.project_file)

    subprocess.call(
        ["coqdoc"] + prj.args +
        shlex.split(DEFAULT_ARGS) +
        ["-d", args.target_dir] +
        prj.coq_files)
    os.unlink(os.path.join(args.target_dir, "coqdoc.css"))

    for fname in prj.html_files:
        fname = os.path.join(args.target_dir, fname)
        fix(fname)

if __name__ == '__main__':
    main()

