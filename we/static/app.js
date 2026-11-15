// People page: filter the list by name and kind, keeping the query in the address.
(function(){
  var box=document.getElementById('people'); if(!box) return;
  var q=document.getElementById('q'), k=document.getElementById('k'), out=document.getElementById('count');
  var items=[].slice.call(box.querySelectorAll('li')), heads=[].slice.call(box.querySelectorAll('h2'));
  var p=new URLSearchParams(location.search); q.value=p.get('q')||''; k.value=p.get('kind')||'';
  function norm(s){return s.normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();}
  function run(){
    var t=norm(q.value.trim()), kk=k.value, n=0;
    items.forEach(function(li){var ok=(!t||norm(li.dataset.n).indexOf(t)>=0)&&(!kk||li.dataset.k.indexOf(kk)>=0); li.hidden=!ok; if(ok)n++;});
    heads.forEach(function(h){var ul=h.nextElementSibling; h.hidden=!ul.querySelector('li:not([hidden])');});
    out.textContent=(t||kk)? n+' matching':'';
    var u=new URLSearchParams(); if(q.value.trim())u.set('q',q.value.trim()); if(kk)u.set('kind',kk);
    history.replaceState(null,'',location.pathname+(u.toString()?'?'+u:''));
  }
  q.addEventListener('input',run); k.addEventListener('change',run); run();
})();
// Sortable tables
document.querySelectorAll('table.sortable th').forEach(function(th,i){
  th.setAttribute('tabindex','0'); th.setAttribute('role','button');
  function sort(){var tb=th.closest('table').tBodies[0], rows=[].slice.call(tb.rows), asc=th.dataset.asc!=='1';
    rows.sort(function(a,b){var x=a.cells[i].textContent.trim(), y=b.cells[i].textContent.trim(), nx=parseFloat(x), ny=parseFloat(y);
      var c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:x.localeCompare(y); return asc?c:-c;});
    rows.forEach(function(r){tb.appendChild(r);}); th.dataset.asc=asc?'1':'0';}
  th.addEventListener('click',sort); th.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();sort();}});
});
