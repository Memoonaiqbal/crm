# import base64
# import json
# import frappe
# import requests
# from frappe import _
# from werkzeug.wrappers import Response
# from frappe.utils import now_datetime, get_datetime, add_to_date
# from crm.integrations.api import get_contact_by_phone_number
# from .ringcentral_handler import IncomingCall, RingCentral, RingCentralCallDetails
# from json import dumps
# from frappe import db
# from datetime import datetime
# from zoneinfo import ZoneInfo
# @frappe.whitelist()
# def is_enabled():
# """Check if RingCentral integration is enabled."""
# return frappe.db.get_single_value("CRM RingCentral Settings", "enabled")
# @frappe.whitelist()
# def get_record_calls():
# """Check if automatic call recording is enabled."""
# return frappe.db.get_single_value("CRM RingCentral Settings", "record_calls")
# @frappe.whitelist()
# def get_webphone_credentials():
# """Returns credentials for RingCentral WebPhone SDK."""
# try:
# ringcentral = RingCentral.connect()
# if not ringcentral:
# frappe.log_error("RingCentral integration not enabled", "RingCentral")
# return {"ok": False, "error": "integration_not_enabled"}
# # Check and refresh token if needed
# if ringcentral.settings.token_expiry and now_datetime() >= get_datetime(ringcentral.settings.token_expiry):
# frappe.log_error("Refreshing access token due to expiry", "RingCentral")
# ringcentral.refresh_access_token()
# # Validate and clean access token
# access_token = ringcentral.settings.access_token
# if not access_token:
# frappe.log_error("No access token found", "RingCentral")
# return {"ok": False, "error": "invalid_access_token", "detail": "No access token found"}
# access_token = access_token.strip() # Remove whitespace
# frappe.log_error("Access token cleaned", f"RingCentral: Cleaned access token: {access_token}")
# # Calculate expires_in
# expires_in = None
# if ringcentral.settings.token_expiry:
# expires_in = int((get_datetime(ringcentral.settings.token_expiry) - now_datetime()).total_seconds())
# from_number = db.get_value("CRM Telephony Agent", frappe.session.user, "ringcentral_number")
# if not from_number:
# frappe.log_error(f"No ringcentral_number for user {frappe.session.user}", "RingCentral")
# return {
# "ok": False,
# "error": "caller_phone_identity_missing",
# "detail": f"No ringcentral_number found for user {frappe.session.user}"
#             }
# # Direct POST request with requests library
# headers = {
# "Authorization": f"Bearer {access_token}",
# "Content-Type": "application/json",
# "Accept": "application/json"
#         }
# frappe.log_error("Sending SIP provision request", f"RingCentral: Headers: {dumps(headers, indent=2)}")
# response = requests.post(
# f"{ringcentral.server_url}/restapi/v1.0/client-info/sip-provision",
# json={"sipInfo": [{"transport": "WSS"}]},
# headers=headers
#         )
# response.raise_for_status()
# sip_response = response.json()
# frappe.log_error("SIP response received", f"RingCentral: {dumps(sip_response, indent=2)}")
# sip_info = sip_response.get('sipInfo', [{}])[0]
# if not sip_info.get('username'):
# frappe.log_error("SIP info missing username", "RingCentral")
# return {
# "ok": False,
# "error": "sip_provision_failed",
# "detail": "Failed to retrieve SIP credentials"
#             }
# return {
# "ok": True,
# "client_id": ringcentral.client_id,
# "client_secret": ringcentral.client_secret,
# "server_url": ringcentral.server_url,
# "token": access_token, # Use access_token as token
# "expires_in": expires_in, # Calculated from token_expiry
# "from_number": from_number,
# "sipInfo": {
# "username": sip_info.get("username"),
# "password": sip_info.get("password"),
# "authorizationId": sip_info.get("authorizationId"),
# "domain": sip_info.get("domain"),
# "outboundProxy": sip_info.get("outboundProxy"),
# "transport": sip_info.get("transport", "WSS")
#             }
#         }
# except Exception as e:
# frappe.log_error(f"WebPhone Credentials Error: {str(e)}", f"RingCentral: {frappe.get_traceback()}")
# return {"ok": False, "error": str(e), "detail": frappe.get_traceback()}
# @frappe.whitelist(allow_guest=True)
# def oauth_callback():
# """Handle OAuth callback from RingCentral"""
# code = frappe.form_dict.get('code')
# if not code:
# frappe.log_error("OAuth callback error: No code provided")
# return '<script>window.close();</script>'
# try:
# ringcentral = RingCentral.connect()
# if not ringcentral:
# frappe.log_error("OAuth callback error: RingCentral integration not enabled")
# return '<script>alert("RingCentral integration not enabled"); window.close();</script>'
# token_url = f"{ringcentral.server_url}/restapi/oauth/token"
# client_id = ringcentral.client_id
# client_secret = ringcentral.client_secret
# auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
# headers = {
# "Authorization": f"Basic {auth_header}",
# "Content-Type": "application/x-www-form-urlencoded"
#         }
# data = {
# "grant_type": "authorization_code",
# "code": code,
# "redirect_uri": ringcentral.redirect_uri,
#         }
# res = requests.post(token_url, data=data, headers=headers)
# if res.status_code != 200:
# frappe.log_error(f"OAuth callback error: Failed to fetch token: {res.text}")
# frappe.throw(_("Failed to fetch token: ") + res.text)
# tokens = res.json()
# frappe.log_error(f"OAuth callback success: Token data={tokens}")
# ringcentral.settings.access_token = tokens["access_token"]
# ringcentral.settings.refresh_token = tokens["refresh_token"]
# ringcentral.settings.token_expiry = add_to_date(now_datetime(), seconds=tokens.get("expires_in", 3600))
# ringcentral.settings.save(ignore_permissions=True)
# frappe.db.commit()
# ringcentral.platform.auth().set_data({
# "access_token": tokens["access_token"],
# "refresh_token": tokens["refresh_token"],
# "expires_in": tokens.get("expires_in", 3600)
#         })
# return '<script>window.opener.postMessage("OAuth flow completed. You can close this window.", "*"); window.close();</script>'
# except Exception as e:
# frappe.log_error(f"OAuth callback error: {str(e)}")
# return f'<script>alert("Authorization failed: {str(e)}"); window.close();</script>'
# @frappe.whitelist()
# def get_authorize_url():
# """Get RingCentral authorization URL."""
# try:
# ringcentral = RingCentral.connect()
# if not ringcentral:
# frappe.log_error(title="RingCentral Authorize URL", message="RingCentral integration is not enabled")
# frappe.throw(_("RingCentral integration is not enabled"))
# auth_url = ringcentral.get_authorize_url()
# frappe.log_error(title="RingCentral Authorize URL", message=f"Generated URL: {auth_url}")
# return {"authorize_url": auth_url}
# except Exception as e:
# frappe.log_error(title="RingCentral Authorize URL Error", message=f"Failed to get authorize URL: {str(e)}\nStacktrace: {frappe.get_traceback()}")
# raise
# @frappe.whitelist()
# def check_auth_status():
# """Check the authorization status of RingCentral integration."""
# settings = frappe.get_doc("CRM RingCentral Settings", "CRM RingCentral Settings")
# if not settings.enabled:
# frappe.log_error("RingCentral integration is disabled in CRM RingCentral Settings")
# return {"is_authorized": False}
# has_valid_token = settings.access_token and (
# not settings.token_expiry or now_datetime() < get_datetime(settings.token_expiry)
#     )
# if not has_valid_token and settings.refresh_token:
# try:
# ringcentral = RingCentral.connect()
# frappe.log_error("Attempting to refresh access token")
# ringcentral.refresh_access_token()
# settings.reload()
# has_valid_token = settings.access_token and (
# not settings.token_expiry or now_datetime() < get_datetime(settings.token_expiry)
#             )
# frappe.log_error(f"Token refresh result: has_valid_token={has_valid_token}")
# except Exception as e:
# frappe.log_error(f"Token refresh failed: {str(e)}")
# frappe.log_error(f"Auth status: has_valid_token={has_valid_token}, access_token={bool(settings.access_token)}, token_expiry={settings.token_expiry}")
# return {"is_authorized": has_valid_token}
# @frappe.whitelist(allow_guest=True)
# def ringcentral_call_handler(**kwargs):
# """Webhook for RingCentral incoming and outgoing call events."""
# try:
# args = frappe._dict(kwargs)
# frappe.log_error(
# title="RingCentral Webhook Received",
# message=f"Webhook payload: {frappe.as_json(args)}"
#         )
# call_details = RingCentralCallDetails(args)
# # Create call log - only once
# create_call_log(call_details)
# if call_details.get_direction() == "Incoming":
# resp = IncomingCall(args.get("fromNumber"), args.get("toNumber")).process()
# frappe.log_error(
# title="RingCentral Incoming Call Processed",
# message=f"Incoming call response: {frappe.as_json(resp)}"
#             )
# if isinstance(resp, dict) and resp.get("status") == "error":
# return Response(json.dumps(resp), mimetype="application/json")
# return Response(json.dumps(resp), mimetype="application/json")
# else:
# # For outgoing calls, update the call log with initial details
# update_call_log(call_sid=call_details.call_sid, status=args.get("callStatus"))
# frappe.log_error(
# title="RingCentral Outgoing Call Processed",
# message=f"Updated call log for call_sid: {call_details.call_sid}, status: {args.get('callStatus')}"
#             )
# return Response(json.dumps({"status": "ok"}), mimetype="application/json")
# except Exception as e:
# frappe.log_error(
# title="RingCentral Webhook Error",
# message=f"Failed to process webhook: {str(e)}\n{frappe.get_traceback()}"
#         )
# return Response(json.dumps({"status": "error", "message": str(e)}), mimetype="application/json")
# @frappe.whitelist()
# def create_call_log(call_details):
# """Create placeholder CRM Call Log at call start. Full sync happens at end."""
# try:
# call_details = frappe._dict(call_details)
# frappe.log_error(
# title="Create Call Log Attempt",
# message=f"Attempting to create call log with details: {frappe.as_json(call_details)}"
#                     )
# if not call_details.get("id"):
# frappe.log_error(title="Create Call Log Error", message="Missing call_sid in call_details")
# return {"ok": False, "error": "Missing call_sid"}
# existing_log = frappe.db.get_value("CRM Call Log", {"id": call_details.get("id")}, "name")
# if existing_log:
# frappe.log_error(
# title="Create Call Log Error",
# message=f"Call log already exists for call_sid: {call_details.get('id')}"
#                             )
# return {"ok": True, "call_sid": existing_log}
# call_log = frappe.get_doc({
# "doctype": "CRM Call Log",
# "id": call_details.get("id"), # telephonySessionId
# "from": call_details.get("from"),
# "to": call_details.get("to"),
# "type": call_details.get("type", "Outgoing"),
# "status": "Initiated", # Placeholder
# "telephony_medium": "RingCentral",
# "start_time": get_datetime_from_timestamp(call_details.get("startTime")),
#                 })
# if call_details.get("type") == "Incoming":
# call_log.receiver = call_details.get("receiver", "")
# contact_number = call_details.get("from")
# else:
# call_log.caller = call_details.get("caller", frappe.session.user)
# contact_number = call_details.get("from") if call_details.get("type") == "Incoming" else call_details.get("to")
# # link(contact_number, call_log)
# if contact_number:
# link(contact_number, call_log)
# call_log.insert(ignore_permissions=True)
# frappe.db.commit()
# return {"ok": True, "call_sid": call_log.name}
# except Exception as e:
# frappe.log_error(title="Create Call Log Error", message=str(e))
# return {"ok": False, "error": str(e)}
# def link(contact_number, call_log):
# contact = get_contact_by_phone_number(contact_number)
# if contact.get("name"):
# doctype = "Contact"
# docname = contact.get("name")
# if contact.get("lead"):
# doctype = "CRM Lead"
# docname = contact.get("lead")
# elif contact.get("deal"):
# doctype = "CRM Deal"
# docname = contact.get("deal")
# call_log.link_with_reference_doc(doctype, docname)
# # @frappe.whitelist(allow_guest=True)
# # def update_call_log(call_sid=None, status=None, duration=None, end_time=None):
# # """Update call log status and details."""
# # try:
# # if not call_sid:
# # frappe.log_error(
# # title="RingCentral Update Call Log",
# # message="No call_sid provided for update_call_log"
# # )
# # return {"status": "error", "message": "No call_sid provided"}
# # # Find call log by id field
# # call_log_name = frappe.db.get_value("CRM Call Log", {"id": call_sid}, "name")
# # if not call_log_name:
# # frappe.log_error(
# # title="RingCentral Update Call Log",
# # message=f"Call log not found for call_sid (id): {call_sid}"
# # )
# # return {"status": "error", "message": f"Call log not found for call_sid: {call_sid}"}
# # call_log = frappe.get_doc("CRM Call Log", call_log_name)
# # # Update fields
# # call_log.status = RingCentralCallDetails.get_call_status(status)
# # call_log.duration = duration
# # call_log.end_time = get_datetime_from_timestamp(end_time) if end_time else frappe.utils.now()
# # call_log.save(ignore_permissions=True)
# # frappe.db.commit()
# # frappe.log_error(
# # title="RingCentral Call Log Updated",
# # message=f"Updated call log: {call_log.name}, call_sid: {call_sid}, status: {call_log.status}, duration: {call_log.duration}"
# # )
# # return {
# # "status": "ok",
# # "message": "Call log updated",
# # "call_log": {
# # "name": call_log.name,
# # "id": call_log.id,
# # "status": call_log.status,
# # "duration": call_log.duration,
# # "end_time": call_log.end_time
# # }
# # }
# # except Exception as e:
# # frappe.log_error(
# # title="RingCentral Update Call Log Error",
# # message=f"Failed to update call log for call_sid: {call_sid}: {str(e)}\n{frappe.get_traceback()}"
# # )
# # frappe.db.commit()
# # return {"status": "error", "message": str(e)}
# @frappe.whitelist(allow_guest=True)
# def update_call_log(call_sid=None, status=None, duration=None, end_time=None):
# """Update call log status and details."""
# try:
# if not call_sid:
# frappe.log_error(
# title="RingCentral Update Call Log",
# message="No call_sid provided for update_call_log"
#             )
# return {"status": "error", "message": "No call_sid provided"}
# call_log_name = frappe.db.get_value("CRM Call Log", {"id": call_sid}, "name")
# if not call_log_name:
# frappe.log_error(
# title="RingCentral Update Call Log",
# message=f"Call log not found for call_sid (id): {call_sid}"
#             )
# return {"status": "error", "message": f"Call log not found for call_sid: {call_sid}"}
# call_log = frappe.get_doc("CRM Call Log", call_log_name)
# call_log.status = RingCentralCallDetails.get_call_status(status)
# call_log.duration = duration
# call_log.end_time = get_datetime_from_timestamp(end_time) if end_time else frappe.utils.now()
# call_log.save(ignore_permissions=True)
# frappe.db.commit()
# frappe.log_error(
# title="RingCentral Call Log Updated",
# message=f"Updated call log: {call_log.name}, call_sid: {call_sid}, status: {call_log.status}, duration: {call_log.duration}"
#         )
# # Fetch recording if call is completed and record_calls is enabled
# if call_log.status in ["Completed", "No Answer"] and frappe.db.get_single_value("CRM RingCentral Settings", "record_calls"):
# recording_response = fetch_call_recording(call_sid)
# if not recording_response.get("ok"):
# frappe.log_error(
# title="RingCentral Recording Fetch Failed",
# message=f"Failed to fetch recording for call_sid: {call_sid}: {recording_response.get('error')}"
#                 )
# return {
# "status": "ok",
# "message": "Call log updated",
# "call_log": {
# "name": call_log.name,
# "id": call_log.id,
# "status": call_log.status,
# "duration": call_log.duration,
# "end_time": call_log.end_time,
# "recording_url": call_log.recording_url
#             }
#         }
# except Exception as e:
# frappe.log_error(
# title="RingCentral Update Call Log Error",
# message=f"Failed to update call log for call_sid: {call_sid}: {str(e)}\n{frappe.get_traceback()}"
#         )
# frappe.db.commit()
# return {"status": "error", "message": str(e)}
# @frappe.whitelist()
# def fetch_call_recording(call_sid):
# """Fetch recording metadata for a call from RingCentral Call Log API and update CRM Call Log."""
# try:
# ringcentral = RingCentral.connect()
# if not ringcentral:
# frappe.log_error("RingCentral integration not enabled", "RingCentral")
# return {"ok": False, "error": "integration_not_enabled"}
# # Check and refresh token if needed
# if ringcentral.settings.token_expiry and now_datetime() >= get_datetime(ringcentral.settings.token_expiry):
# frappe.log_error("Refreshing access token due to expiry", "RingCentral")
# ringcentral.refresh_access_token()
# # Fetch call log details for the specific telephonySessionId
# headers = {
# "Authorization": f"Bearer {ringcentral.settings.access_token.strip()}",
# "Content-Type": "application/json",
# "Accept": "application/json"
#         }
# response = requests.get(
# f"{ringcentral.server_url}/restapi/v1.0/account/~/call-log?telephonySessionId={call_sid}&recordingType=All&view=Detailed",
# headers=headers
#         )
# response.raise_for_status()
# call_data = response.json()
# records = call_data.get("records", [])
# if not records:
# frappe.log_error(f"No call log records found for telephonySessionId: {call_sid}", "RingCentral")
# return {"ok": False, "error": "no_call_log_found"}
# # Sort recordings by startTime
# recordings = []
# for record in records:
# if record.get("recording"):
# recordings.append({
# "id": record["recording"]["id"],
# "uri": record["recording"]["uri"],
# "contentUri": record["recording"]["contentUri"],
# "type": record["recording"]["type"],
# "startTime": record.get("startTime")
#                 })
# recordings.sort(key=lambda x: x["startTime"] if x["startTime"] else "")
# if not recordings:
# frappe.log_error(f"No recordings found for telephonySessionId: {call_sid}", "RingCentral")
# return {"ok": False, "error": "no_recording_found"}
# # For simplicity, use the first recording's contentUri
# # For multi-leg calls, you may need to combine recordings (see below)
# primary_recording = recordings[0]
# call_log_name = frappe.db.get_value("CRM Call Log", {"id": call_sid}, "name")
# if not call_log_name:
# frappe.log_error(f"Call log not found for telephonySessionId: {call_sid}", "RingCentral")
# return {"ok": False, "error": f"Call log not found for telephonySessionId: {call_sid}"}
# # Update CRM Call Log with the primary recording URL
# frappe.db.set_value("CRM Call Log", call_log_name, "recording_url", primary_recording["contentUri"])
# frappe.db.commit()
# frappe.log_error(
# title="RingCentral Recording Updated",
# message=f"Updated call log {call_log_name} with recording URL: {primary_recording['contentUri']}"
#         )
# # # Optionally, handle multi-leg recordings (example: combine into a single file)
# # if len(recordings) > 1:
# # combined_url = combine_recordings(recordings, headers, call_sid)
# # if combined_url:
# # frappe.db.set_value("CRM Call Log", call_log_name, "recording_url", combined_url)
# # frappe.db.commit()
# # frappe.log_error(
# # title="RingCentral Combined Recording Updated",
# # message=f"Updated call log {call_log_name} with combined recording URL: {combined_url}"
# # )
# # return {
# # "ok": True,
# # "recording": primary_recording,
# # "additional_recordings": recordings[1:] if len(recordings) > 1 else []
# # }
# except Exception as e:
# frappe.log_error(
# title="RingCentral Fetch Recording Error",
# message=f"Failed to fetch recording for telephonySessionId: {call_sid}: {str(e)}\n{frappe.get_traceback()}"
#         )
# return {"ok": False, "error": str(e)}
# def get_datetime_from_timestamp(timestamp):
# """Convert timestamp to system timezone datetime."""
# if not timestamp:
# return None
# datetime_utc = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
# system_timezone = frappe.utils.get_system_timezone()
# converted_datetime = datetime_utc.astimezone(ZoneInfo(system_timezone))
# return frappe.utils.format_datetime(converted_datetime, "yyyy-MM-dd HH:mm:ss")
# api.py code
# import frappe
# from frappe import _
# import requests
# from ringcentral import SDK
# from crm.integrations.ringcentral.utils import get_public_url, merge_dicts
# from frappe.utils.password import get_decrypted_password
# from frappe.utils import now_datetime, add_to_date, get_datetime
# import base64
# @frappe.whitelist(allow_guest=True)
# def oauth_callback(code=None, state=None):
# if not code:
# frappe.throw(_("Missing authorization code."))
# settings = frappe.get_single("CRM RingCentral Settings")
# token_url = f"{settings.server_url}/restapi/oauth/token"
# client_id = settings.client_id
# client_secret = settings.get_password("client_secret")
# auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
# headers = {
# "Authorization": f"Basic {auth_header}",
# "Content-Type": "application/x-www-form-urlencoded"
#     }
# data = {
# "grant_type": "authorization_code",
# "code": code,
# "redirect_uri": settings.redirect_uri,
#     }
# res = requests.post(token_url, data=data, headers=headers)
# if res.status_code != 200:
# frappe.throw(_("Failed to fetch token: ") + res.text)
# tokens = res.json()
# frappe.log_error(
# title="RingCentral Tokens Debug",
# message=res.text
#     )
# settings.access_token = tokens["access_token"]
# settings.refresh_token = tokens["refresh_token"]
# settings.token_expiry = add_to_date(now_datetime(), seconds=tokens.get("expires_in", 3600))
# settings.save(ignore_permissions=True)
# frappe.db.commit()
# frappe.local.response["type"] = "redirect"
# frappe.local.response["location"] = "/crm"
# class RingCentral:
# """RingCentral connector over RingCentral SDK."""
# def __init__(self, settings):
# """
#         :param settings: `CRM RingCentral Settings` doctype
#         """
# self.settings = settings
# self.client_id = settings.client_id
# self.client_secret = settings.get_password("client_secret")
# self.server_url = settings.server_url
# self.redirect_uri = settings.redirect_uri
# self.rcsdk = self.get_ringcentral_client()
# self.platform = self.rcsdk.platform() # Expose platform attribute
# def get_authorize_url(self):
# """Generate RingCentral OAuth URL (for frontend button)."""
# return (
# f"{self.server_url}/restapi/oauth/authorize"
# f"?response_type=code"
# f"&client_id={self.client_id}"
# f"&redirect_uri={self.redirect_uri}"
#         )
# def refresh_access_token(self):
# """Refresh expired token."""
# if not self.settings.refresh_token:
# frappe.log_error("Missing refresh token in CRM RingCentral Settings", title="RingCentral Token Refresh Error")
# frappe.throw(_("Missing refresh token."))
# token_url = f"{self.server_url}/restapi/oauth/token"
# client_id = self.settings.client_id
# client_secret = self.settings.get_password("client_secret")
# auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
# headers = {
# "Authorization": f"Basic {auth_header}",
# "Content-Type": "application/x-www-form-urlencoded"
#         }
# data = {
# "grant_type": "refresh_token",
# "refresh_token": self.settings.get_password("refresh_token")
#         }
# res = requests.post(token_url, headers=headers, data=data)
# if res.status_code != 200:
# frappe.log_error(message=res.text, title="RingCentral Token Refresh Failed")
# frappe.throw(_("Failed to refresh token: ") + res.text)
# tokens = res.json()
# frappe.log_error(
# message=frappe.as_json({
# "access_token": tokens["access_token"][:50] + "...",
# "refresh_token": tokens["refresh_token"][:50] + "...",
# "expires_in": tokens.get("expires_in", 3600),
# "scope": tokens.get("scope")
#             }),
# title="RingCentral Token Refreshed"
#         )
# self.settings.access_token = tokens["access_token"]
# self.settings.refresh_token = tokens["refresh_token"]
# self.settings.token_expiry = add_to_date(now_datetime(), seconds=tokens.get("expires_in", 3600))
# self.settings.save(ignore_permissions=True)
# frappe.db.commit()
# self.platform.auth().set_data({
# "access_token": tokens["access_token"],
# "refresh_token": tokens["refresh_token"],
# "expires_in": tokens.get("expires_in", 3600)
#         })
# return self.settings.access_token
# def fetch_call_log_by_session(self, telephony_session_id, view='Detailed', account_level=False):
# """Fetch call log from RC API by telephonySessionId."""
# try:
# endpoint = '/restapi/v1.0/account/~/call-log' if account_level else '/restapi/v1.0/account/~/extension/~/call-log'
# params = {
# 'telephonySessionId': telephony_session_id,
# 'view': view,
# 'perPage': 1 # Since we filter by unique ID, expect 1 result
#                             }
# response = self.platform.get(endpoint, params=params)
# data = response.json()
# if not data.get('records'):
# frappe.log_error(f"No call log found for telephonySessionId: {telephony_session_id}", "RingCentral Fetch Call Log")
# return None
# except Exception as e:
# frappe.log_error(f"Failed to fetch call log: {str(e)}", "RingCentral Fetch Call Log")
# return None
# @classmethod
# def connect(cls):
# """Make a RingCentral connection."""
# settings = frappe.get_doc("CRM RingCentral Settings")
# if not (settings and settings.enabled):
# frappe.log_error("RingCentral integration is not enabled")
# return None
# return cls(settings=settings)
# def get_phone_numbers(self):
# """Get account's RingCentral phone numbers."""
# try:
# url = f"{self.server_url}/restapi/v1.0/account/~/phone-number"
# headers = {
# "Authorization": f"Bearer {self.settings.access_token.strip()}",
# "Content-Type": "application/json"
#             }
# response = requests.get(url, headers=headers)
# if response.status_code != 200:
# frappe.log_error(title="Failed to fetch phone numbers", message=response.text)
# frappe.throw(_("Failed to fetch phone numbers: ") + response.text)
# numbers = response.json().get("records", [])
# return [n["phoneNumber"] for n in numbers if n.get("usageType") == "DirectNumber"]
# except Exception as e:
# frappe.log_error(title="Failed to fetch phone numbers", message=str(e))
# frappe.throw(_("Failed to fetch phone numbers: ") + str(e))
# def generate_access_token(self, identity: str, ttl=3600):
# """Generates a token for WebRTC authentication."""
# try:
# if not self.platform.auth().access_token_valid():
# if self.settings.token_expiry and now_datetime() >= get_datetime(self.settings.token_expiry):
# frappe.log_error("Access token expired, refreshing...")
# self.refresh_access_token()
# token_data = self.platform.auth().data()
# frappe.log_error(f"Generated token data: {token_data}")
# return {
# 'token': token_data.get('access_token'),
# 'expires_in': token_data.get('expires_in', 3600)
#             }
# except Exception as e:
# frappe.log_error(
# title="Generated RingCentral Token",
# message=frappe.as_json(token_data) # pretty prints JSON into message field
#             )
# return {}
# @classmethod
# def safe_identity(cls, identity: str):
# # """Create a safe identity by replacing unsupported characters."""
# return identity.replace("@", "(at)")
# @classmethod
# def emailid_from_identity(cls, identity: str):
# """Convert safe identity string into emailID."""
# return identity.replace("(at)", "@")
# def generate_ringcentral_dial_response(self, from_number: str, to_number: str):
# """Generates call instructions to forward the call to agent's phone."""
# try:
# url = f"{self.server_url}/restapi/v1.0/account/~/extension/~/ring-out"
# headers = {
# "Authorization": f"Bearer {self.settings.access_token.strip()}",
# "Content-Type": "application/json",
# "Accept": "application/json"
#             }
# data = {
# "from": {"phoneNumber": from_number},
# "to": {"phoneNumber": to_number},
# "playPrompt": True
#             }
# response = requests.post(url, headers=headers, json=data)
# if response.status_code != 200:
# frappe.log_error(title="Failed to generate RingCentral dial response", message=response.text)
# frappe.throw(_("Failed to generate dial response: ") + response.text)
# return response.json()
# except Exception as e:
# frappe.log_error(title="Failed to generate RingCentral dial response", message=str(e))
# return {}
# def get_call_info(self, call_sid):
# """Fetch call details by call ID."""
# try:
# response = self.platform.get(f'/restapi/v1.0/account/~/telephony/sessions/{call_sid}')
# return response.json()
# except Exception as e:
# frappe.log_error(title="Failed to fetch RingCentral call info", message=str(e))
# return {}
# def get_ringcentral_client(self):
# """Initialize RingCentral SDK client."""
# if not self.settings.enabled:
# frappe.throw(_("Please enable RingCentral settings before making a call."))
# if self.settings.token_expiry:
# token_expiry = get_datetime(self.settings.token_expiry)
# if now_datetime() >= token_expiry:
# frappe.log_error("Access token expired, refreshing in get_ringcentral_client...")
# self.refresh_access_token()
# rcsdk = SDK(self.client_id, self.client_secret, self.server_url)
# if self.settings.access_token:
# clean_access_token = self.settings.access_token.strip()
# rcsdk.platform().auth().set_data({
# 'access_token': clean_access_token,
# 'refresh_token': self.settings.get_password("refresh_token"),
# 'expires_in': 3600
#             })
# return rcsdk
# class IncomingCall:
# def __init__(self, from_number, to_number, meta=None):
# self.from_number = from_number
# self.to_number = to_number
# self.meta = meta
# def process(self):
# """Process the incoming call."""
# ringcentral = RingCentral.connect()
# if not ringcentral:
# return {"status": "error", "message": _("RingCentral not enabled")}
# owners = get_ringcentral_number_owners(self.to_number)
# attender = get_the_call_attender(owners, self.from_number)
# if not attender:
# return {"status": "error", "message": _("Agent is unavailable to take the call, please call after some time.")}
# if attender["call_receiving_device"] == "Phone":
# return ringcentral.generate_ringcentral_dial_response(self.from_number, attender["mobile_no"])
# else:
# return {
# "status": "client",
# "identity": ringcentral.safe_identity(attender["name"])
#             }
# def get_ringcentral_number_owners(phone_number):
# """Get list of users who are using the phone_number."""
# phone_number = "".join([c for c in phone_number if c.isdigit() or c == "+"])
# user_voice_settings = frappe.get_all(
# "CRM Telephony Agent",
# filters={"ringcentral_number": phone_number},
# fields=["name", "call_receiving_device"],
#     )
# user_wise_voice_settings = {user["name"]: user for user in user_voice_settings}
# user_general_settings = frappe.get_all(
# "User", filters=[["name", "IN", user_wise_voice_settings.keys()]], fields=["name", "mobile_no"]
#     )
# user_wise_general_settings = {user["name"]: user for user in user_general_settings}
# return merge_dicts(user_wise_general_settings, user_wise_voice_settings)
# def get_active_loggedin_users(users):
# """Filter the current logged-in users from the given users list."""
# rows = frappe.db.sql(
# """
#         SELECT `user`
#         FROM `tabSessions`
#         WHERE `user` IN %(users)s
#         """,
#         {"users": users},
#     )
# return [row[0] for row in set(rows)]
# def get_the_call_attender(owners, caller=None):
# """Get attender details from list of owners."""
# if not owners:
# return
# current_loggedin_users = get_active_loggedin_users(list(owners.keys()))
# if len(current_loggedin_users) > 1 and caller:
# deal_owner = frappe.db.get_value("CRM Deal", {"mobile_no": caller}, "deal_owner")
# if not deal_owner:
# deal_owner = frappe.db.get_value(
# "CRM Lead", {"mobile_no": caller, "converted": False}, "lead_owner"
#             )
# for user in current_loggedin_users:
# if user == deal_owner:
# current_loggedin_users = [user]
# for name, details in owners.items():
# if (details["call_receiving_device"] == "Phone" and details["mobile_no"]) or (
# details["call_receiving_device"] == "Computer" and name in current_loggedin_users
#         ):
# return details
# class RingCentralCallDetails:
# def __init__(self, call_info, call_from=None, call_to=None):
# self.call_info = call_info
# self.call_sid = call_info.get("id")
# self.call_status = self.get_call_status(call_info.get("status", {}).get("callStatus"))
# self._call_from = call_from or call_info.get("from", {}).get("phoneNumber")
# self._call_to = call_to or call_info.get("to", {}).get("phoneNumber")
# def get_direction(self):
# if self.call_info.get("direction") == "Outbound":
# return "Outgoing"
# return "Incoming"
# def get_from_number(self):
# return self._call_from or self.call_info.get("from", {}).get("phoneNumber")
# def get_to_number(self):
# return self._call_to or self.call_info.get("to", {}).get("phoneNumber")
# @classmethod
# def get_call_status(cls, ringcentral_status):
# """Convert RingCentral given status into system status."""
# ringcentral_status = ringcentral_status or ""
# if not ringcentral_status:
# return "Unknown"
# return " ".join(ringcentral_status.replace("-", " ").split()).title()
# def to_dict(self):
# """Convert call details into dict."""
# direction = self.get_direction()
# from_number = self.get_from_number()
# to_number = self.get_to_number()
# caller = ""
# receiver = ""
# if direction == "Outgoing":
# caller = self.call_info.get("from", {}).get("name", "")
# identity = RingCentral.safe_identity(caller)
# caller = RingCentral.emailid_from_identity(identity) if identity else ""
# else:
# owners = get_ringcentral_number_owners(to_number)
# attender = get_the_call_attender(owners, from_number)
# receiver = attender["name"] if attender else ""
# return {
# "type": direction,
# "status": self.call_status,
# "id": self.call_sid,
# "from": from_number,
# "to": to_number,
# "receiver": receiver,
# "caller": caller,
#         }
