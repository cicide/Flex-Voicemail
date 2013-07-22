<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Edit User</%def>
<div id="details">
	<a href="/">Back</a>
	<table border='2' style="float: left;">
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
        	<td><a href="/user/edit/${user.id}">Edit</a> / <a href="/user/delete/${user.id}">Delete</a></td>
        </tr>
		% endfor
	</table>
</div>
