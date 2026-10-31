/**
 * Bee Role Definitions
 * Centralized configuration for all bee roles
 */
export const BEE_ROLES = {
  juiz: {
    key: 'juiz',
    label: 'Juiz',
    color: '#4caf50',
    emoji: '⚖️',
    accessory: 'toga',
    workstation: 'bench',
    description: 'Orquestra tarefas, eleição, health checks'
  },
  guarda: {
    key: 'guarda',
    label: 'Guarda',
    color: '#2196f3',
    emoji: '🛡️',
    accessory: 'police_hat',
    workstation: 'gate',
    description: 'Auditoria, segurança, GuardianPatrol'
  },
  bibliotecaria: {
    key: 'bibliotecaria',
    label: 'Bibliotecária',
    color: '#9c27b0',
    emoji: '📚',
    accessory: 'glasses_books',
    workstation: 'desk',
    description: 'Índice global, roteamento, fallback web'
  },
  artista: {
    key: 'artista',
    label: 'Artista',
    color: '#e91e63',
    emoji: '🎨',
    accessory: 'labcoat_palette',
    workstation: 'studio',
    description: 'Worker especializado em tarefas criativas'
  },
  trabalhadora: {
    key: 'trabalhadora',
    label: 'Trabalhadora',
    color: '#ffb300',
    emoji: '👷',
    accessory: 'helmet',
    workstation: 'factory',
    description: 'Worker genérico, executa plugins'
  },
  idle: {
    key: 'idle',
    label: 'Ociosa',
    color: '#888888',
    emoji: '🐝',
    accessory: 'none',
    workstation: 'hive_cell',
    description: 'Sem papel atribuído'
  }
};

/** Map cluster_role from API to our internal keys */
export const ROLE_MAP = {
  'juiz': 'juiz',
  'guarda': 'guarda',
  'bibliotecario': 'bibliotecaria',
  'bibliotecaria': 'bibliotecaria',
  'worker_artist': 'artista',
  'artista': 'artista',
  'worker': 'trabalhadora',
  'trabalhadora': 'trabalhadora',
  'idle': 'idle',
  '': 'idle'
};

/** Get role definition from API cluster_role */
export function getRole(clusterRole) {
  const key = ROLE_MAP[clusterRole?.toLowerCase?.() || ''] || 'idle';
  return BEE_ROLES[key];
}

/** Get all roles as array */
export function getAllRoles() {
  return Object.values(BEE_ROLES);
}

/** Get role color */
export function getRoleColor(clusterRole) {
  return getRole(clusterRole).color;
}

/** Get role emoji */
export function getRoleEmoji(clusterRole) {
  return getRole(clusterRole).emoji;
}