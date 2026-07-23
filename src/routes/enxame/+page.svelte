<script lang="ts">
	import MissionControl from '$lib/components/enxame/MissionControl.svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	// Opcional: Redirecionar se o usuário não estiver autenticado
	// (O Open WebUI lida com auth globalmente, mas isso garante acesso seguro)
	let isLoading = true;

	onMount(async () => {
		// Simula um carregamento rápido ou verifica permissões se necessário
		// No Open WebUI, se o usuário chegou aqui, ele já passou pelo auth global do layout
		isLoading = false;

		// Opcional: Forçar tema escuro se desejar
		document.documentElement.classList.add('dark');
	});
</script>

<svelte:head>
	<title>Enxame Mission Control | Open WebUI</title>
	<meta name="description" content="Orquestração de IA avançada com Enxame OS" />
</svelte:head>

{#if isLoading}
	<div class="flex items-center justify-center h-screen bg-gray-900 text-white">
		<div class="text-center">
			<div
				class="animate-spin rounded-full h-12 w-12 border-b-2 border-green-400 mx-auto mb-4"
			></div>
			<p class="font-mono text-green-400">Inicializando Enxame OS...</p>
		</div>
	</div>
{:else}
	<!-- Renderiza o componente principal do Enxame -->
	<MissionControl />
{/if}

<style>
	/* Garante que o fundo seja consistente com o tema industrial */
	:global(body) {
		background-color: #0f1115;
		margin: 0;
		padding: 0;
	}
</style>
