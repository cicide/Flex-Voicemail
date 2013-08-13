<%inherit file="/home.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Voicemail Inbox</%def>
<script type="text/javascript" src="http://mediaplayer.yahoo.com/js"></script>

<%block name="subHeading">
	<form id="custom-search-form" action='/search' method='post' class="form-search form-horizontal pull-right">
	    <div class="input-append span12">
	        <input type="text" name="search"  class="search-query" placeholder="Search">
	        <button type="submit" class="btn"><i class="icon-search"></i></button>
	        <a class="btn btn-small" href="/">Back</a>
	    </div>
	</form>
</%block>

<%block name="DetailView">
	<div id="details">
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
			%if not voicemails:
				<div class="alert alert-info">  
				  <a class="close" data-dismiss="alert">×</a>  
				  <strong>Info!</strong>There are no voice mails available.  
				</div>  
			%endif
	</div>
</%block>