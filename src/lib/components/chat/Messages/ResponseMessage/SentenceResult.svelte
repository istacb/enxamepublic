<script lang="ts">
  import { labels } from '$lib/locales';

  export let message = '';
  export let errorMessage = '';
</script>

<div>
  <div class="result-box fade-in">
    <p>{message}</p>
  </div>

  {#if errorMessage}
    <div class="result-box error-box fade-in">
      <p><strong>⚠️ {labels.error}:</strong> {errorMessage}</p>
    </div>
  {/if}
</div>

<style>
  .result-box {
    padding: 12px;
    border-radius: 8px;
    margin-top: 8px;
  }

  .error-box {
    background-color: #fee;
    border: 1px solid #fcc;
    color: #c00;
  }

  .fade-in {
    animation: fadeIn 0.3s ease-in;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
</style>
