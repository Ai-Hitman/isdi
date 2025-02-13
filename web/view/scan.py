import json
import config
import os
from web import app
from web.view.index import get_device
from flask import render_template, request, session
from db import (get_client_devices_from_db, new_client_id, create_scan, 
    create_mult_appinfo)

@app.route("/scan", methods=['POST', 'GET'])
def scan():
    """
    Needs three attribute for a device
    :param device: "android" or "ios" or test
    :return: a flask view template
    """
    #clientid = request.form.get('clientid', request.args.get('clientid'))
    if 'clientid' not in session:
        return redirect(url_for('index'))

    device_primary_user = request.form.get(
        'device_primary_user',
        request.args.get('device_primary_user'))
    device = request.form.get('device', request.args.get('device'))
    action = request.form.get('action', request.args.get('action'))
    device_owner = request.form.get(
        'device_owner', request.args.get('device_owner'))

    currently_scanned = get_client_devices_from_db(session['clientid'])
    template_d = dict(
        task="home",
        title=config.TITLE,
        device=device,
        device_primary_user=config.DEVICE_PRIMARY_USER,   # TODO: Why is this sent
        device_primary_user_sel=device_primary_user,
        apps={},
        currently_scanned=currently_scanned,
        clientid=session['clientid']
    )
    # lookup devices scanned so far here. need to add this by model rather
    # than by serial.
    print('CURRENTLY SCANNED: {}'.format(currently_scanned))
    print('DEVICE OWNER IS: {}'.format(device_owner))
    print('PRIMARY USER IS: {}'.format(device_primary_user))
    print('-' * 80)
    print('CLIENT ID IS: {}'.format(session['clientid']))
    print('-' * 80)
    print("--> Action = ", action)

    sc = get_device(device)
    if not sc:
        template_d["error"] = "Please choose one device to scan."
        return render_template("main.html", **template_d), 201
    if not device_owner:
        template_d["error"] = "Please give the device a nickname."
        return render_template("main.html", **template_d), 201

    ser = sc.devices()

    print("Devices: {}".format(ser))
    if not ser:
        # FIXME: add pkexec scripts/ios_mount_linux.sh workflow for iOS if
        # needed.
        error = "<b>A device wasn't detected. Please follow the "\
            "<a href='/instruction' target='_blank' rel='noopener'>"\
            "setup instructions here.</a></b>"
        template_d["error"] = error
        return render_template("main.html", **template_d), 201

    ser = first_element_or_none(ser)
    # clientid = new_client_id()
    print(">>>scanning_device", device, ser, "<<<<<")

    if device == "ios":
        error = "If an iPhone is connected, open iTunes, click through the "\
                "connection dialog and wait for the \"Trust this computer\" "\
                "prompt to pop up in the iPhone, and then scan again."
    else:
        error = "If an Android device is connected, disconnect and reconnect "\
                "the device, make sure developer options is activated and USB "\
                "debugging is turned on on the device, and then scan again."
    error += "{} <b>Please follow the <a href='/instruction' target='_blank'"\
             " rel='noopener'>setup instructions here,</a> if needed.</b>"
    if device == 'ios':
        # go through pairing process and do not scan until it is successful.
        isconnected, reason = sc.setup()
        template_d["error"] = error.format(reason)
        template_d["currently_scanned"] = currently_scanned
        if not isconnected:
            return render_template("main.html", **template_d), 201

    # TODO: model for 'devices scanned so far:' device_name_map['model']
    # and save it to scan_res along with device_primary_user.
    device_name_print, device_name_map = sc.device_info(serial=ser)

    # Finds all the apps in the device
    # @apps have appid, title, flags, TODO: add icon
    apps = sc.find_spyapps(serialno=ser).fillna('').to_dict(orient='index')
    if len(apps) <= 0:
        print("The scanning failed for some reason.")
        error = "The scanning failed. This could be due to many reasons. Try"\
            " rerunning the scan from the beginning. If the problem persists,"\
            " please report it in the file. <code>report_failed.md</code> in the<code>"\
            "phone_scanner/</code> directory. Checn the phone manually. Sorry for"\
            " the inconvenience."
        template_d["error"] = error
        return render_template("main.html", **template_d), 201

    scan_d = {
        'clientid': session['clientid'],
        'serial': config.hmac_serial(ser),
        'device': device,
        'device_model': device_name_map.get('model', '<Unknown>').strip(),
        'device_version': device_name_map.get('version', '<Unknown>').strip(),
        'device_primary_user': device_owner,
    }

    if device == 'ios':
        scan_d['device_manufacturer'] = 'Apple'
        scan_d['last_full_charge'] = 'unknown'
    else:
        scan_d['device_manufacturer'] = device_name_map.get(
            'brand', "<Unknown>").strip()
        scan_d['last_full_charge'] = device_name_map.get(
            'last_full_charge', "<Unknown>")

    rooted, rooted_reason = sc.isrooted(ser)
    scan_d['is_rooted'] = rooted
    scan_d['rooted_reasons'] = json.dumps(rooted_reason)

    # TODO: here, adjust client session.
    scanid = create_scan(scan_d)

    if device == 'ios':
        pii_fpath = sc.dump_path(ser, 'Device_Info')
        print('Revelant info saved to db. Deleting {} now.'.format(pii_fpath))
        cmd = os.unlink(pii_fpath)
        # s = catch_err(run_command(cmd), msg="Delete pii failed", cmd=cmd)
        print('iOS PII deleted.')

    print("Creating appinfo...")
    create_mult_appinfo([(scanid, appid, json.dumps(
        info['flags']), '', '<new>') for appid, info in apps.items()])

    currently_scanned = get_client_devices_from_db(session['clientid'])
    template_d.update(dict(
        isrooted=(
            "<strong class='text-info'>Maybe (this is possibly just a bug with our scanning tool).</strong> Reason(s): {}"
            .format(rooted_reason) if rooted
            else "Don't know" if rooted is None 
            else "No"
        ),
        device_name=device_name_print,
        apps=apps,
        scanid=scanid,
        sysapps=set(),  # sc.get_system_apps(serialno=ser)),
        serial=ser,
        currently_scanned=currently_scanned,
        # TODO: make this a map of model:link to display scan results for that
        # scan.
        error=config.error()
    ))
    return render_template("main.html", **template_d), 200
 

def first_element_or_none(l):
    if l and len(l) > 0:
        return l[0]


