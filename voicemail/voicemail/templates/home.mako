<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Home</%def>
<div id="details">
    <div class="menu">
        <p>Welcome ${user.name}</p>
        <ul>
        <li> <a href="/user/add"> Add user </a> </li>
        <li> <a href="/user/edit"> Edit user </a </li> 
        <li> Remove </li>
        <li> Search </li>
        </ul>
    </div>
</div>
