"""
Binds a 3dsmax executable as a rez package.
"""
from __future__ import absolute_import
from win32api import GetFileVersionInfo, LOWORD, HIWORD

import os
import sys
import functools
from pkg_resources import resource_filename, Requirement

from rez.bind._utils import check_version, find_exe, extract_version, make_dirs
from rez.package_maker__ import make_package
from rez.system import system
from rez.utils.platform_ import platform_
from rez.vendor.version.version import Version


def setup_parser(parser):
    parser.add_argument("--root", type=str, metavar="PATH",
                        help="the folder in which Photoshop was installed to.")


def win_commands(exepath):
    return '''env.PATH.append(r\'{0}\')'''.format(exepath)


def bind(path, version_range=None, opts=None, parser=None):
    if platform_.name != 'windows':
        raise EnvironmentError('Only binds on windows at the moment')

    # find executable, determine version
    if opts and opts.root:
        bin_path = opts.root
        try:
            info = GetFileVersionInfo(os.path.join(bin_path, 'Photoshop.exe'), "\\")
            ms = info['FileVersionMS']
            ls = info['FileVersionLS']
            version = Version('{}.{}.{}.{}'.format(HIWORD(ms), LOWORD(ms), HIWORD(ls), LOWORD(ls)))
        except:
            raise EnvironmentError('Unknown version')
    else:
        installed_versions = []
        adobe_root = r'C:\Program Files\Adobe'
        app_folder_prefix = 'Adobe Photoshop'
        for app_folder in os.listdir(adobe_root):
            if app_folder.startswith(app_folder_prefix):
                app_exe = os.path.join(adobe_root, app_folder, 'Photoshop.exe')
                if os.path.exists(app_exe):
                    try:
                        info = GetFileVersionInfo(app_exe, "\\")
                        ms = info['FileVersionMS']
                        ls = info['FileVersionLS']
                        version = Version('{}.{}.{}.{}'.format(HIWORD(ms), LOWORD(ms), HIWORD(ls), LOWORD(ls)))
                    except:
                        raise EnvironmentError('Unknown version')
                    installed_versions.append(
                        (app_folder, version)
                    )

        if len(installed_versions) < 1:
            raise EnvironmentError(
                'Unable to find any installed version of 3ds Max under "{}"'.format(
                    adobe_root
                )
            )

        app_folder, version = sorted(installed_versions, key=lambda v: v[1])[-1]

        bin_path = os.path.join(adobe_root, app_folder)

    check_version(version, version_range)

    def make_root(resources_path, variant, path):
        import shutil
        shutil.copy(
            os.path.join(resources_path, 'Photoshop_icon.png'),
            os.path.join(path, 'Photoshop_icon.png')
        )

    make_root_partial = functools.partial(make_root, resource_filename(Requirement.parse('rez'), "rez/bind/resources"))

    with make_package("photoshop", path, make_root=make_root_partial) as pkg:
        pkg.version = version
        pkg.tools = ["photoshop"]
        pkg.description = 'Painting Application'
        pkg.authors = ['Adobe']
        pkg.requires = []
        pkg.nice_name = 'Photoshop'

        pkg.tools_info = {
            'photoshop': {
                'command': ['start', 'Photoshop', '/D', '%REZ_PHOTOSHOP_ROOT%', '/wait', '/B', 'Photoshop.exe'],
                'nice_name': 'Photoshop',
                'priority': 89,
                'icon': '{root}/Photoshop_icon.png',
                'launch_in_prompt': False
            }
        }
        pkg.commands = win_commands(bin_path)
        pkg.variants = [system.variant]

    return "photoshop", version
