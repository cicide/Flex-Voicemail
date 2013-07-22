<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Delete User</%def>
<div id="details">
	<a href="/">Back</a>
	<table border='1'>
		<tr>
			<th>Name</th>
		</tr>
		% for user in users:
		<tr>
        	<td><a href="/user/edit/${user.id}">${user.name}</a></td>
        </tr>
		% endfor
	</table>
</div>
