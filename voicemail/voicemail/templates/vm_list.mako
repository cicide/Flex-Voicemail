<%inherit file="/home.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Voicemail Inbox</%def>
<script type="text/javascript" src="http://mediaplayer.yahoo.com/js"></script>
<%block name="main_content">
	<div id="details">
		<a href="/">Back</a>
		<table class="table">
			<tr>
				<th>Message</th>
				<th>Status</th>
				<th>Duration</th>
				<th>Create Date</th>
				<th>CID Name</th>
				<th>CID Number</th>
				<th>Action</th>
			</tr>
			%for vm in voicemails:
				<tr>
					<td>
						<a href="#">
							%if vm.is_read:
								${vm.path.split('/')[len(vm.path.split('/'))-1:].pop()}
							%else:
								<b>${vm.path.split('/')[len(vm.path.split('/'))-1:].pop()}</b>
							%endif
						</a>
					</td>
					<td>${vm.status}</td>
					<td>${vm.duration}</td>
					<td>${vm.create_date}</td>
					<td>${vm.cid_name}</td>
					<td>${vm.cid_number}</td>
					<td>
						<a href="/vm/play/${vm.id}">Play</a>
						<a href="/vm/download/${vm.id}">Download</a>
						<a href="#">Delete</a>
					</td>
				</tr>
			%endfor
		</table>
	</div>
</%block>