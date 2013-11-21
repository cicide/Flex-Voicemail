<%inherit file="/home.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Voicemail Users</%def>

<%block name="subHeading">
<a class="btn btn-small pull-right" href="/">Back</a>
</%block>
<%block name="DetailView">
	<div id="details">
		
		<table id="users_list" class="table table-striped table-bordered table-condensed">
			<tr>
				<th>ID</th>
				<th>Name</th>
				<th>Username</th>
				<th>Extension</th>
				<th>Pin</th>
				<th>Status</th>
				<th>VM pref </th>
				<th>Action</th>
			</tr>
			% for user in users:
			<tr>
	        	<td>${user.id}</td>
	        	<td>${user.name}</td>
	        	<td>${user.username}</td>
	        	<td>${user.extension}</td>
	        	<td>${user.pin}</td>
	        	<td>${user.status}</td>
	        	<td><a href="/vmpref/edit/${user.id}">Edit</a></td>
	        	<td> <div class="btn-group inline">
				        <a class="btn btn-small" href="/user/edit/${user.id}">Edit</a>
				        %if user == request.user:
				        	<div class="btn btn-small disabled">Delete</div>
				        %else:
				        	<div class="btn btn-small" onclick="showModal('${user.id}','${user.username}')">Delete</div>
				        %endif
				    </div>
    			</td>
	        </tr>
			% endfor
		</table>
	</div>
	<%include file="./delete_user.mako"/>

</%block>
