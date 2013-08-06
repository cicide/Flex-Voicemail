<%inherit file="/home.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Voicemail Preference</%def>

<%block name="subHeading">
<a class="btn btn-small pull-right" href="/vmpref/edit">Edit</a>
</%block>

<%block name="DetailView">
		<div class="pagination-left">
			  <label>Folder:
			  <span>${vmpref['folder']}</span></label>
			  <label>Deliver VM:
			  <span>${vmpref['deliver_vm']}</span></label>
			  <label>Attach VM:
			  <span>${vmpref['attach_vm']}</span></label>
			  <label>Email:
			  <span>${vmpref['email']}</span></label>
			  <label>SMS Addr:
			  <span>${vmpref['sms_addr']}</span></label>
			  <label>VM Greeting:
			  <span>${vmpref['vm_greeting']}</span></label>
			  <label>VM Name Recording:
			  <span>${vmpref['vm_name_recording']}</span></label>
		</div>
</%block>