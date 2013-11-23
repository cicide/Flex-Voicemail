<li class="nav-header">Options</li>
%if utils.has_permission('admin'):
	<li> <a href="/user/add"> Add user </a> </li>
	<li> <a href="/users/list/vmusers"> User Configuration </a> </li>
	<li> <a href="/users/list/admins"> Manage Admins </a> </li>
	<li> <a href="/list/lists"> Manage Lists </a> </li>
%endif
<li> <a href="/vm/view"> Voicemails </a> </li>
<li> <a href="/user/pref"> Preferences </a> </li>  
