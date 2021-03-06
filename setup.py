#!/usr/bin/env python

__author__      = "Remi Chateauneu"
__copyright__   = "Copyright 2020-2021, Primhill Computers"
__license__     = "GPL"

import os
import sys

import ast

# pip install ..\dist\survol-1.0.dev0.zip --upgrade --install-option="--port 12345"

# TODO: Have a look to setuptools.setup
from distutils import log
from distutils.core import setup
from setuptools import find_packages

from setuptools.command.install import install
from setuptools.command.install_lib import install_lib

is_py2 = sys.version_info < (3,)

if is_py2:
    from future_builtins import filter

# https://stackoverflow.com/questions/677577/distutils-how-to-pass-a-user-defined-parameter-to-setup-py
#
# pip install -v displays methods calls and their outputs.
#
# The following methods are called, see -v option:
#    running install
#    Running initialize_options.


class InstallCommand(install):
    # The html files can be copied at any place.
    # For example at ~/public_html on Unix, i.e. "Users Dir feature of Apache".
    # TODO: These options are not used yet.
    user_options = install.user_options + [
        ('port=', 'p', 'CGI server port number'),       # Not used at the moment.
        ('www=', 'w', 'Web UI destination directory'),  # Not used at the moment.
    ]

    def initialize_options(self):
        print("Running initialize_options")
        install.initialize_options(self)
        self.port = 24680 # TODO: This is not used yet.

        # By default, cgiserver will pick its files from the Python installation directory,
        # and this is acceptable because they are part of the same package.

        # http://setuptools.readthedocs.io/en/latest/setuptools.html#automatic-script-creation
        # For the default destination of HTML pages, see also "pkg_resources" and the likes:
        # "The distutils normally install general "data files" to a platform-specific location (e.g. /usr/share)"
        # So it is possible to install the HTML pages in a normal directory, and also in a location,
        # standard for Python, where Python modules can retrieve them. and also the Python server.
        self.www = None

    def finalize_options(self):
        print('The port number for install is:%s' % self.port)
        install.finalize_options(self)

    def run(self):
        #This must be given to a parameter file for cgiserver.
        my_port = self.port

        # The HTML, css and js files must be copied at this place.
        # This avoids to have a HTTP server such as Apache or IIS,
        # pick its files from the Python installation dir.
        my_www = self.www

        # Also, the css and js files must be copied into the Python directory.

        print("Custom installation. Port:%s Dest dir=%s" % (my_port,my_www))
        if my_www:
            print("About to copy %s" % my_www)
        install.run(self)  # OR: install.do_egg_install(self)


class InstallLibCommand(install_lib):
    """
    On Linux and Darwin, this converts Python files to proper Unix format, and sets the executable flag.
    This is needed because setup.py does not keep the executable flag information.
    Also, files stored in Github have Windows lines terminators.
    """

    def _transform_linux_script(self, one_path):
        with open(one_path, 'rb') as input_stream:
            file_content = input_stream.readlines()

        if len(file_content) == 0:
            log.info("InstallLibCommand empty file=%s" % one_path)
            return

        # By convention, all Survol CGI scritps start with this header line.
        # There must not be any CR character after this shebang line.
        if file_content[0].startswith(b"#!/usr/bin/env python"):
            log.info("Script file=%s l=%d" % (one_path, len(file_content)))
            try:
                # Maybe this file is a script. If so, remove "CRLF" at the end.
                lines_number = 0
                with open(one_path, 'wb') as output_stream:
                    for one_line in file_content:
                        if one_line.endswith((b'\r\n', b'\n\r')):
                            output_stream.write(b"%s\n" % one_line[:-2])
                        else:
                            output_stream.write(one_line)
                        lines_number += 1

                log.info("Script written=%d" % lines_number)
                # Set executable flag for Linux CGI scripts.
                os.chmod(one_path, 0o744)
            except Exception as exc:
                log.error("Script err=%s" % exc)

    def copy_tree(
            self, infile, outfile,
            preserve_mode=1, preserve_times=1, preserve_symlinks=0, level=1
    ):
        """This is called on Linux and Darwin, from the top-level infile='build\\lib' """
        if sys.platform.startswith("lin") or sys.platform == "darwin":
            library_top = os.path.join(infile, "survol")
            for library_root, library_dirs, library_files in os.walk(library_top):
                for one_file in library_files:
                    if one_file.endswith(".py"):
                        one_path = os.path.join(library_root, one_file)
                        self._transform_linux_script(one_path)

        return install_lib.copy_tree(self, infile, outfile,
            preserve_mode, preserve_times, preserve_symlinks, level)


# Some explanations: The Python scripts in survol/sources_types (Plus some of them
# in survol/ like survol/entity.py etc...) are CGI scripts.
# Therefore, they can easily be run, debugged and tested in isolation, without a HTTP server.
# These scripts can also be imported: This is how the WSGI server works.
# Some CGI scripts could easily be rewritten in another language for performance.

# The current directory is where setup.py is.
def package_files(directory):
    paths = []
    for path, directories, filenames in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join('..', path, filename))
    return paths


# HTML and Javascript files for the D3 interface.
extra_files = package_files('survol/www')

# This file is needed for the events generators processes, started by the package supervisor.
extra_files += ['survol/scripts/supervisord.conf']

# The zip archive contains directories: docs, survol and tests.

# This extracts the version number for the file "survol/__init__.py"
with open(os.path.join('survol', '__init__.py')) as f:
    __version__ = ast.parse(next(filter(lambda line: line.startswith('__version__'), f))).body[0].value.s

with open('README.txt') as readme_file:
    README = readme_file.read()

# FIXME: Cleanup the doc strings, for example survol.__doc__ = '\nSurvol library\n' ...


required_packages = ['psutil', 'rdflib']
if is_py2:
    required_packages.append("configparser")

setup(
    name='survol',
    version=__version__,
    description='Exploring legacy IT systems',
    long_description=README,
    author='Primhill Computers',
    author_email='contact@primhillcomputers.com',
    url='http://www.primhillcomputers.com/survol.html',
    packages=find_packages(),
    package_dir = {"survol": "survol"},
    # This is apparently not recursive.
    package_data={'survol': extra_files},
    entry_points={'console_scripts': [
        'survolcgi = survol.scripts.cgiserver:cgiserver_entry_point',
        'survolwsgi = survol.scripts.wsgiserver:wsgiserver_entry_point',
        'dockit = survol.scripts.wsgiserver:dockit_entry_point',
    ]},
    # These packages are not needed to run dockit.py which is strictly standalone.
    install_requires=required_packages,
    cmdclass={
        'install': InstallCommand,
        'install_lib': InstallLibCommand,
    },

    scripts=['survol/scripts/cgiserver.py', 'survol/scripts/wsgiserver.py', 'survol/scripts/dockit.py'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Education',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: Python Software Foundation License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: JavaScript',
        'Topic :: Software Development :: Bug Tracking',
        'Topic :: Education',
        'Topic :: Software Development :: Documentation',
        'Topic :: System :: Systems Administration',
        'Topic :: Documentation'
    ]
    )

################################################################################

# APPENDIX: Some tips about the installation of Survol under Apache.
#
# Two installations types are possible:
# (1) With the CGI scripts cgiserver, which just need to be accessible,
# and imports survol Python modules, installed by sdist.
# (2) Or if Apache runs the sources files from the development directory or from the installed packages.
# This is what is demonstrated here.

#Alias /Survol "C:/Users/rchateau/Developpement/ReverseEngineeringApps/PythonStyle"
#<Directory "C:/Users/rchateau/Developpement/ReverseEngineeringApps/PythonStyle" >
#    Options Indexes FollowSymLinks Includes ExecCGI
#    Allow from all
#    AddHandler cgi-script .py
#	# http://stackoverflow.com/questions/2036577/how-do-i-ignore-the-perl-shebang-on-windows-with-apache-2
#	ScriptInterpreterSource Registry-Strict
#	# SetEnv PYTHONPATH C:\Users\rchateau\Developpement\ReverseEngineeringApps\PythonStyle\survol\revlib
#</Directory>

################################################################################

## Appendix'appendix: How to install Yawn, which is an HTML navigator into OpenLmi (Pegasus) objects and classes.
## apache's configuration file for yawn using wsgi
## We could add this content in yawn.conf and incldue the content.
#WSGIScriptAlias /yawn "C:/Users/rchateau/Developpement/ReverseEngineeringApps/pywbem_all/pywbem_sourceforge/yawn2/trunk/mod_wsgi/yawn_wsgi.py"

## For development convenience, no need to install anything because we point to the development files.
#<Directory "C:/Users/rchateau/Developpement/ReverseEngineeringApps/pywbem_all/pywbem_sourceforge/yawn2/trunk/mod_wsgi>
#    # Options Indexes FollowSymLinks Includes ExecCGI
#    Options ExecCGI
#    # Allow from all
#    WSGIPassAuthorization On
#    # AddHandler cgi-script .py
#	# http://stackoverflow.com/questions/2036577/how-do-i-ignore-the-perl-shebang-on-windows-with-apache-2
#	# ScriptInterpreterSource Registry-Strict
#	SetEnv PYTHONPATH C:\Users\rchateau\Developpement\ReverseEngineeringApps\pywbem_all\pywbem_sourceforge\yawn2\trunk\mod_wsgi\pywbem_yawn
#</Directory>

################################################################################

# TODO: How to display optional modules ? Which features do they provide ?