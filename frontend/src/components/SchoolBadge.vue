<script setup>
// The Bona School crest — recreated as an inline SVG so it stays crisp at any
// size, needs no network fetch, and prints reliably on receipts/report cards.
defineProps({
    size: { type: Number, default: 96 }
});
</script>

<template>
  <svg :width="size" :height="size * 0.95" viewBox="0 0 200 190" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="The Bona School badge — In Truth We Excel">
    <!-- Shield -->
    <path d="M16 24
             Q42 8 66 16
             Q100 2 134 16
             Q158 8 184 24
             L177 98
             Q170 152 100 184
             Q30 152 23 98 Z"
          fill="#262626" stroke="#111111" stroke-width="3" />
    <path d="M24 30
             Q45 17 67 24
             Q100 11 133 24
             Q155 17 176 30
             L170 96
             Q163 146 100 175
             Q37 146 30 96 Z"
          fill="none" stroke="#f5f5f4" stroke-width="2" opacity="0.35" />

    <!-- School name -->
    <text x="100" y="58" text-anchor="middle" fill="#ffffff"
          font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="21" letter-spacing="1">THE BONA</text>
    <text x="100" y="82" text-anchor="middle" fill="#ffffff"
          font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="21" letter-spacing="2">SCHOOL</text>

    <!-- TBS monogram, stepped like the crest -->
    <text x="62" y="122" text-anchor="middle" fill="#ffffff"
          font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="34">T</text>
    <text x="97" y="130" text-anchor="middle" fill="#ffffff"
          font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="36">B</text>
    <text x="133" y="138" text-anchor="middle" fill="#ffffff"
          font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="34">S</text>

    <!-- Motto ribbon -->
    <path d="M30 136 Q100 180 170 136" fill="none" stroke="#f5f5f4" stroke-width="1.6" opacity="0.9" />
    <path id="bona-motto-arc" d="M30 148 Q100 192 170 148" fill="none" />
    <text fill="#ffffff" font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="12.5" letter-spacing="1">
      <textPath href="#bona-motto-arc" startOffset="50%" text-anchor="middle">IN TRUTH WE EXCEL</textPath>
    </text>
  </svg>
</template>
