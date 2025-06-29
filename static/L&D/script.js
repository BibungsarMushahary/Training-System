document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('trainingModal');
  const deptNameSpan = document.getElementById('deptName');
  const deptInput = document.getElementById('department');
  const closeBtn = document.querySelector('.close');


  document.querySelectorAll('.dept-card').forEach(card => {
    card.addEventListener('click', function() {
      const dept = this.getAttribute('data-dept');
      deptNameSpan.textContent = dept;
      deptInput.value = dept;
      modal.style.display = 'block';
    });
  });

  closeBtn.addEventListener('click', function() {
    modal.style.display = 'none';
  });

  window.addEventListener('click', function(event) {
    if (event.target === modal) {
      modal.style.display = 'none';
    }
  });
});