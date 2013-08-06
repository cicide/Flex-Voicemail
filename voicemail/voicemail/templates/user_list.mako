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
				        <div class="btn btn-small" onclick="handleClick('/user/edit','${user.id}')">Edit</div>
				        %if user == request.user:
				        	<div class="btn btn-small disabled">Delete</div>
				        %else:
				        	<div class="btn btn-small" onclick="handleClick('/user/delete','${user.id}')">Delete</div>
				        %endif
				    </div>
    			</td>
	        </tr>
			% endfor
		</table>
	</div>
	<script>
		function handleClick(url,userid) {
		  
		  var url = this.location.origin + url;
		  data = {'userid': userid}
		  $.post(url, data, function(response) {
	  			newAlert(response.success, response.msg);
	  			window.setTimeout(function(){location.reload()},5000)
			}, 'json');
		}
		
		function newAlert (success, message) {
			if (success == true ){
				$("#alert-area").append($("<div class='alert alert-success alert-message'><a class='close' data-dismiss='alert'>×</a><strong>Success! </strong>"+message+"</div>"));
			}
			else{
				$("#alert-area").append($("<div class='alert alert-error alert-message'><a class='close' data-dismiss='alert'>×</a><strong>Success! </strong>"+message+"</div>"));
			}					
			
		    $(".alert-message").delay(5000).fadeOut("slow", function () { $(this).remove(); });
		}
		
	</script>
</%block>