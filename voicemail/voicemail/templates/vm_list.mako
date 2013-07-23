<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Voicemail Inbox</%def>
<div id="details">
	<a href="/">Back</a>
	<table border='2' style="float: left;">
		<tr>
			<th>Message</th>
			<th>Status</th>
			<th>Duration</th>
			<th>Create Date</th>
			<th>CID Name</th>
			<th>CID Number</th>
		</tr>
		%for vm in voicemails:
			<tr>
				<td>
					<a href="#">
						%if vm.is_read:
							${vm.path}
						%else:
							<b>${vm.path}</b>
						%endif
					</a>
				</td>
				<td>${vm.status}</td>
				<td>${vm.duration}</td>
				<td>${vm.create_date}</td>
				<td>${vm.cid_name}</td>
				<td>${vm.cid_number}</td>
			</tr>
		%endfor
	</table>
</div>
