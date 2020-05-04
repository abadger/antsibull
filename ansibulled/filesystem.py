# coding: utf-8
# Author: Toshio Kuratomi <tkuratom@redhat.com>
# License: GPLv3+
# Copyright: Ansible Project, 2020
"""Entrypoint to the ansibulled-docs script."""

import sh

try:
    import posix1e
except ImportError:
    posix1e = None


class UnableToCheck(Exception):
    """No library or command support to check this."""


class CheckFailure(Exception):
    """We checking failed unexpectedly."""


def writable_via_acls(path: str, euid: int) -> bool:
    """
    Check whether acls gives someone other than the user write access to a path.

    :arg path: Pathname to check.
    :arg euid: userid to identify the user by.
    :returns: True if acls give someone other than the user path write access to the path.
    """
    # Check acls if available
    acls = None
    if posix1e:
        acl = posix1e.ACL(file=path)
        acls = acl.to_any_text(options=posix1e.TEXT_NUMERIC_IDS).decode('utf-8')
    else:
        try:
            acls = sh.getfacl(path, '-n').stdout.decode('utf-8')
        except sh.CommandNotFound:
            pass
        except Exception as e:
            raise CheckFailure(f'Error while trying to get acls for {path}: {e}')

    if not acls:
        raise UnableToCheck(f'No way to determine acls for {path}')

    mask_has_write = True
    principal_has_write = False

    for acl in (a for a in acls.splitlines() if not a.startswith('#')):
        type_, principal, permissions = acl.rsplit(':', 2)
        # default acls have the same issues as acls directly on the directory
        if type_.startwith('default:'):
            dummy_, type_ = type_.split(':', 1)

        # All the safe things:

        # ACL is for the user themselves
        if type_ == 'user' and (not principal or principal == euid):
            continue

        if type_ == 'mask':
            # The mask does not allow acls to set write
            if 'w' not in permissions:
                mask_has_write = False
                break
            # No other mask values affect safety
            continue

        # The acl doesn't grant write permission
        if 'w' not in permissions:
            continue

        # Okay, the principal has write in this case
        principal_has_write = True

    if mask_has_write and principal_has_write:
        return True
    return False
