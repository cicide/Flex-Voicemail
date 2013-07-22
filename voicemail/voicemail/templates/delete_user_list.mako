<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Delete User</%def>
<div id="details">
	<a href="/">Back</a>
	<table border='1'>
		<tr>
			<th>ID</th>
			<th>Name</th>
			<th>Username</th>
			<th>Extension</th>
			<th>Pin</th>
			<th>Status</th>
			<th>Delete</th>
		</tr>
		% for user in users:
		<tr>
        	<td>${user.id}</td>
        	<td>${user.name}</td>
        	<td>${user.username}</td>
        	<td>${user.extension}</td>
        	<td>${user.pin}</td>
        	<td>${user.status}</td>
        	<td><a href="/user/delete/${user.id}">X</a></td>
        </tr>
		% endfor
	</table>
</div>
