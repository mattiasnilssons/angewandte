
<script>
  import { page } from '$app/stores';
  import '../app.css'; // global styles
</script>


<div class="container">
  <nav>
    <a href="/" class:active={$page.url.pathname === '/'}>Search</a>
    <a href="/upload" class:active={$page.url.pathname.startsWith('/upload')}>Upload</a>
  </nav>
  <slot />
</div>
