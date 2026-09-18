<template>
  <div class="min-h-screen bg-[#FAF7F1] text-stone-900 antialiased">
    <NuxtPage />
  </div>
</template>

<style>
/* Editorial type pairing: Fraunces (display serif) + Inter (body) */
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap');
:root { --ink: #1C1917; --paper: #FAF7F1; --moss: #1F3D2B; --clay: #B45309; }
body { font-family: 'Inter', system-ui, sans-serif; font-size: 16px; line-height: 1.55; }
.font-display { font-family: 'Fraunces', Georgia, serif; }
:focus-visible { outline: 3px solid #1F3D2B; outline-offset: 2px; border-radius: 4px; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
