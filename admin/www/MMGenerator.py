"""Generator for the Mailman on-line documentation.

Requires ht2html.py, available from

http://www.wooz.org/users/barry/software/pyware.html
"""

import time
import os
import re

from Skeleton import Skeleton
from Sidebar import Sidebar, BLANKCELL
from Banner import Banner
from HTParser import HTParser
from LinkFixer import LinkFixer

COMMA = ','



sitelinks = [
    # Row 1
    ('%(rootdir)s/index.html',  'Home'),
    ('%(rootdir)s/users.html',  'Users'),
    ('http://www.list.org/',    'List.Org'),
    # Row 2
    ('%(rootdir)s/install-start.html',                   'Installation'),
    ('%(rootdir)s/mgrs.html',                            'List Managers'),
    ('http://www.gnu.org/software/mailman/mailman.html', 'Mailman at GNU'),
    # Row 3
    ('%(rootdir)s/faq.html',    'FAQ'),
    ('%(rootdir)s/admins.html', 'Site Administrators'),
    ('http://www.python.org/',  'Python.Org'),
    # Row 4
    ('%(rootdir)s/lists.html',  'Discussion Lists'),
    ('%(rootdir)s/devs.html',   'Developers'),
    ('http://www.gnu.org/',     'Gnu.Org'),
    ]



class MMGenerator(Skeleton, Sidebar, Banner):
    def __init__(self, file, rootdir, relthis):
        self.__body = None
        root, ext = os.path.splitext(file)
        html = root + '.html'
        p = self.__parser = HTParser(file, 'mailman-users@python.org')
        f = self.__linkfixer = LinkFixer(html, rootdir, relthis)
        p.process_sidebar()
        p.sidebar.append(BLANKCELL)
        # massage our links
        self.__d = {'rootdir': rootdir}
        self.__linkfixer.massage(p.sidebar, self.__d)
        # tweak
        p.sidebar.append((None, """\
<center><a href="http://www.python.org/"><img border=0
    src="%(rootdir)s/images/PythonPoweredSmall.png"></a>&nbsp;<a
    href="http://sourceforge.net"><img
    src="http://sourceforge.net/sflogo.php?group_id=103"
    width="88" height="31" border="0"
    alt="SourceForge Logo"></a>
    """ % self.__d))
        p.sidebar.append(BLANKCELL)
        years = COMMA.join([str(x)
                            for x in range(1998, time.localtime()[0]+1)])
        copyright = self.__parser.get('copyright', years)
        p.sidebar.append((None, '&copy; ' + copyright + """\
<br>Free Software Foundation, Inc.<br>
Verbatim copying and distribution of this entire article is permitted in
any medium, provided this notice is preserved.<br>
Please send comments on these pages to <a href="mailto:webmasters@gnu.org">
&lt;webmasters@gnu.org&gt;</a>, other questions to <a
href="mailto:gnu@gnu.org">&lt;gnu@gnu.org&gt;</a>.
"""))
        Sidebar.__init__(self, p.sidebar)
        #
        # fix up our site links, no relthis because the site links are
        # relative to the root of my web pages
        #
        sitelink_fixer = LinkFixer(f.myurl(), rootdir)
        sitelink_fixer.massage(sitelinks, self.__d, aboves=1)
        Banner.__init__(self, sitelinks, cols=3)
        # kludge!
##        for i in range(len(p.sidebar)-1, -1, -1):
##            if p.sidebar[i] == 'Email Us':
##                p.sidebar[i] = 'Email me'
##                break

    def get_corner(self):
        rootdir = self.__linkfixer.rootdir()
        return '''
<center>
    <a href="%(rootdir)s/index.html">
    <img border=0 src="%(rootdir)s/images/logo-70.jpg"></a></center>''' \
    % self.__d

    def get_corner_bgcolor(self):
        return 'black'

    def get_banner(self):
        return Banner.get_banner(self)

    def get_title(self):
        title = self.__parser.get('title')
        return title + ' - GNU Project - Free Software Foundation (FSF)'

    def get_meta(self):
        skel = Skeleton.get_meta(self)
        extra = '\n<LINK REV="made" HREF="mailto:webmasters@www.gnu.org">'
        return skel + extra

    def get_sidebar(self):
        return Sidebar.get_sidebar(self)

    def get_banner_attributes(self):
        return 'CELLSPACING=0 CELLPADDING=0'

    def get_body(self):
        if self.__body is None:
            self.__body = self.__parser.fp.read()
        return self.__body

    def get_lightshade(self):
        """Return lightest of 3 color scheme shade."""
        return '#99997c'

    def get_darkshade(self):
        """Return darkest of 3 color scheme shade."""
        return '#663300'
