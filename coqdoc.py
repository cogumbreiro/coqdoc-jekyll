#!/usr/bin/env python3

from bs4 import BeautifulSoup, NavigableString
import re
import shlex
import os.path
import subprocess

def fix_title(elem, h):
    hdr = elem.find(h, 'section')
    if hdr is not None:
        lbl = hdr.find_previous_sibling('a').extract()
        del hdr['class']
        #hdr = hdr.extract()
        #elem.insert_before(hdr)
        hdr.wrap(lbl)


def replace_with(old_elem, new_elem):
    if isinstance(new_elem, str):
        new_elem = NavigableString(new_elem)
    old_elem.replace_with(new_elem)
    return new_elem

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
    data = re.sub(r'(<br/>\n*)+', r'<br/>', data, flags=re.MULTILINE)
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
        fix_title(elem, 'h1')
        fix_title(elem, 'h2')
        elem.name = 'p'
        for txt in elem.contents:
            if not isinstance(txt, NavigableString): continue
            txt = replace_with(txt, str(txt).strip())
            splits = re.split(r'([ \t]*\n){2,}', str(txt), flags=re.MULTILINE)
            splits = list(x for x in splits if x.strip() != "")
            if len(splits) >= 2:
                part, *rest = splits
                txt = replace_with(txt, part)
                for fragment in rest:
                    p = bs.new_tag('br')
                    p['class'] = "NL"
                    txt.insert_after(p)
                    txt = NavigableString(fragment)
                    p.insert_after(txt)
            
        for div in elem.find_all('pre'):
            p = bs.new_tag('br')
            p['class'] = "PRE"
            div.insert_after(p)
            
        del elem['class']

    for elem in bs.find_all('div', 'code'):
        elem.name = 'pre'
        #del elem['class']

    for elem in bs.find_all('span', 'inlinecode'):
        elem.insert_before(NavigableString(' '))
        elem.insert_after(NavigableString(' '))

    mark = bs.find(text=re.compile('^This page has been generated'))
    if mark is not None:
        mark.find_previous_sibling('hr').decompose()
        mark.find_next_sibling('a').decompose()
        mark.replace_with('')

    for elem in bs.find_all('div'):
        if elem.text.strip() == "":
            elem.decompose()

    #return bs
    data = re.sub(r'<br class="NL"/>', r'</p><p>', str(bs), flags=re.MULTILINE)
    data = data.replace(r'<tt>', r'<code>')
    data = data.replace(r'</tt>', r'</code>')
    data = re.sub(r'<a name="[a-z0-9]+"><h[1-9]>', lambda x: r'</p>' + x.group(0), data, flags=re.MULTILINE)
    data = re.sub(r'</h[1-9]></a>', lambda x: x.group(0) + r'<p>', data, flags=re.MULTILINE)
    data = data.replace(r'<p></p>', '')
    data = data.replace(r'<pre>', '</p><pre>')
    data = data.replace(r'</pre><br class="PRE"/>', '</pre><p>')
    return data
    #return BeautifulSoup(data, 'html.parser').prettify()

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
        fp.write(str(bs))

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

DEFAULT_ARGS = "--body-only --no-index --lib-subtitles -s"

def main():
    import sys, argparse
    parser = argparse.ArgumentParser(description='coqdoc using Tufte CSS.')
    d_target_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    parser.add_argument("-d", default=d_target_dir, dest="target_dir", help="Target directory. Default: %(default)s")
    parser.add_argument("-p", default="_CoqProject", dest="project_file", help="Coq Project file. Default: %(default)s")
    pass_through = [
        ("-l", "light mode (only defs and statements)"),
        ("-g", "(gallina) skip proofs"),
    ]
    for (param, help_desc) in pass_through:
        parser.add_argument(param,
            action="store_const",
            const=[param], default=[],
            help=help_desc)
    parser.add_argument("--extra", dest="extra", nargs="*", default=shlex.split(DEFAULT_ARGS), help="Extra arguments. Default: %(default)s")
    args = parser.parse_args()
    
    extra_args = args.extra
    
    for (param, _) in pass_through:
        if getattr(args, param[1:]):
            extra_args.append(param)

    prj = Project.load(args.project_file)
    cmd = ["coqdoc"] + prj.args + ["-d", args.target_dir] + extra_args + prj.coq_files
    print(" ".join(cmd))
    subprocess.call(cmd)
    os.unlink(os.path.join(args.target_dir, "coqdoc.css"))

    for fname in prj.html_files:
        fname = os.path.join(args.target_dir, fname)
        fix(fname)

if __name__ == '__main__':
    main()

