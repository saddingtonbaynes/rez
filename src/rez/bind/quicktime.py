"""
Binds a quicktime executable as a rez package.
"""
from __future__ import absolute_import

import os
import sys

from rez.bind._utils import check_version
from rez.package_maker__ import make_package
from rez.system import system
from rez.utils.platform_ import platform_
from rez.vendor.version.version import Version


def setup_parser(parser):
    parser.add_argument("--root", type=str, metavar="PATH",
                        help="the folder in which QuickTime was installed to.")


def win_commands(exepath):
    return 'env.PATH.append(r\'{}\')'.format(exepath)


def bind(path, version_range=None, opts=None, parser=None):
    # find executable, determine version
    if opts and opts.root:
        bin_path = opts.root
    else:
        possible_paths = [r'C:\Program Files (x86)\QuickTime']
        for root_path in possible_paths:
            if os.path.exists(root_path):
                bin_path = root_path
                break
        else:
            raise EnvironmentError(
                'Unable to find Quicktime on this system in the paths; {}'.format(
                    ', '.join(possible_paths)
                )
            )

    if platform_.name == 'windows':
        from win32api import GetFileVersionInfo, LOWORD, HIWORD
        try:
            info = GetFileVersionInfo(os.path.join(bin_path, 'QuickTimePlayer.exe'), "\\")
            ms = info['FileVersionMS']
            ls = info['FileVersionLS']
            version = Version('{}.{}.{}.{}'.format(HIWORD(ms), LOWORD(ms), HIWORD(ls), LOWORD(ls)))
        except:
            raise EnvironmentError('Unknown version')
    else:
        raise EnvironmentError('Only binds on windows at the moment')

    check_version(version, version_range)

    with make_package("quicktime", path) as pkg:
        pkg.version = version
        if platform_.name == 'windows':
            pkg.tools = ["QuickTimePlayer.exe"]
            pkg.commands = win_commands(bin_path)
        else:
            raise EnvironmentError('Only binds on windows at the moment')
        pkg.variants = [system.variant]

    return "quicktime", version
