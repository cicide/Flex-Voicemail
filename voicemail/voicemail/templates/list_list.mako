<%inherit file="/home.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">List of Lists</%def>

<%block name="subHeading">
<a class="btn btn-small pull-right" href="/">Back</a>
<a class="btn btn-small pull-right" href="/list/add">Add List</a>
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
			% for mylist in lists:
			<tr>
	        	<td>${mylist.id}</td>
	        	<td>${mylist.name}</td>
	        	<td>${mylist.username}</td>
	        	<td>${mylist.extension}</td>
	        	<td>${mylist.pin}</td>
	        	<td>${mylist.status}</td>
	        	<td><a href="/vmpref/edit/${mylist.id}">Edit</a></td>
	        	<td> <div class="btn-group inline">
				        <a class="btn btn-small" href="/list/edit/${mylist.id}">Edit</a>
				        %if user == request.user:
				        	<div class="btn btn-small disabled">Delete</div>
				        %else:
				        	<div class="btn btn-small" onclick="showModal('${mylist.id}','${mylist.username}')">Delete</div>
				        %endif
				    </div>
    			</td>
	        </tr>
			% endfor
		</table>
	</div>
	<%include file="./delete_list.mako"/>

</%block>
