function toggle(id){
  const el = document.getElementById(id);
  if(!el) return;
  el.style.display = (el.style.display === 'none' || el.style.display === '') ? 'block' : 'none';
}

function toggleClass(id, cls){
  const el = document.getElementById(id);
  if(!el) return;
  el.classList.toggle(cls);
}
