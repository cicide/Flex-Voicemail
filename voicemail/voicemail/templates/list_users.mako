<%inherit file="/home.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Edit List</%def>
<%block name="DetailView">
	<div id="details">
	        %if form:
	          ${form|n}
	        %endif
	    <script type="text/javascript">
	        deform.load()
	    </script>
        <table id="users_list" class="table table-striped table-bordered table-condensed">
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Extension</th>
            </tr>
            % if mylist:
            % for user in mylist.members:
            <tr>
                <td>${user.id}</td>
                <td>${user.name}</td>
                <td>${user.extension}</td>
                <td> <div class="btn-group inline">
                        <a class="btn btn-small" href="/list/users/${mylist.id}/remove/${user.id}">Remove</a>
                    </div>
                </td>
            </tr>
            % endfor
            % endif
        </table>
        %if len(mylist.members)==0:
            <div class="alert alert-info">  
              There are no users in this list.  
            </div>  
        %endif
	</div>
</%block>
