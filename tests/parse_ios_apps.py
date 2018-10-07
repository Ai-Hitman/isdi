#!/usr/bin/env python3
from plistlib import readPlist
from functools import reduce
import operator
import json

# load permissions mappings, apps plist
with open('ios_permissions.json', 'r') as fh:
    PERMISSIONS_MAP = json.load(fh)
APPS_PLIST = plistlib.readPlist('iphone_plist.xml')

def _retrieve(dict_, nest):
    '''
        Navigates dictionaries like dict_[nest0][nest1][nest2]...
    '''
    try:
        return reduce(operator.getitem, nest, dict_)
    except KeyError as e:
        return ""

def _print_permissions(permissions, msg):
    for permission in permissions:
        if permission not in PERMISSIONS_MAP:
            # add newly-discovered permission
            with open('ios_permissions.json', 'w') as fh:
                PERMISSIONS_MAP[permission] = permission[11:]
                fh.write(json.dumps(PERMISSIONS_MAP))
            permission = permission[11:]
        print("\t{}: ".format(msg)+str(PERMISSIONS_MAP[permission]))

def permissions():
    # get xml dump from ios_dump.sh
    for app in APPS_PLIST:
        party = app["ApplicationType"].lower()
        if party in ['system','user']:
            print(app['CFBundleName'],"("+app['CFBundleIdentifier']+") is a {} app and has permissions:"\
                    .format(party))

            permissions = _retrieve(app, ['Entitlements','com.apple.private.tcc.allow'])
            adjustable_permissions =  _retrieve(app, ['Entitlements','com.apple.private.tcc.allow.overridable'])
            PII = _retrieve(app, ['Entitlements','com.apple.private.MobileGestalt.AllowedProtectedKeys'])

            _print_permissions(permissions, "Built-in")
            _print_permissions(adjustable_permissions, "Adjustable from settings")

            if PII:
                print("\tPII: "+str(PII))

        print("")

if __name__ == "__main__":
    permissions()
