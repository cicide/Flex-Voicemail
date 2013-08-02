<li class="nav-header">Options</li>
%if utils.has_permission('admin'):
	<li> <a href="/user/add"> Add user </a> </li>
	<li> <a href="/users/list/vmusers"> User Configuration </a> </li>
	<li> <a href="/users/list/admins"> Manage Admins </a> </li>
%endif
<li> <a href="/vm/view"> Voicemails </a> </li>
<li> <a href="/user/pref"> Preference </a> </li>  
<li> Search </li>
<li class="nav-header">Global Actions</li>
<li><a href="#">sample1</a></li>
<li><a href="#">sample2</a></li>
<li><a href="#">sample3</a></li>
<li><a href="#">sample4</a></li>