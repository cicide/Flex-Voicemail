<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Home</%def>
<div id="details">
    <div>
        <p>Welcome ${user.name}</p>
        <ul>
        <li> <a href="/user/add"> Add user </a> </li>
        <li> <a href="/users/list"> Edit user </a> </li> 
        <li> <a href="/users/list"> Delete user </a> </li>
        <li> Search </li>
        </ul>
    </div>
</div>
