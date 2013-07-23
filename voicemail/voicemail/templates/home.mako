<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Home</%def>
<div id="details">
    <div>
        <p>Welcome ${user.name}</p>
        <ul>
        %if utils.has_permission('admin'):
        <li> <a href="/user/add"> Add user </a> </li>
        <li> <a href="/users/list"> User Configuration </a> </li>
        %endif
        <li> <a href="/vm/view"> Voicemails </a> </li>  
        <li> Search </li>
        </ul>
    </div>
</div>
