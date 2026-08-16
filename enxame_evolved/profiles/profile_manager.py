"""
Profile Manager — Gerenciamento de Perfis de Agentes
====================================================
Cria, armazena, versiona e seleciona perfis de agentes
baseados em capacidades, especialidades e performance histórica.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from enxame_evolved.agents.evolved_agent import AgentProfile, AgentCapability

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentProfileSpec:
    """Especificação para criar/atualizar um perfil."""
    agent_id: str
    name: str
    capabilities: list[AgentCapability]
    specialties: list[str] = field(default_factory=list)
    model: str = "llama3.2:3b"
    system_prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_profile_id: str | None = None  # Para versionamento


class ProfileManager:
    """
    Gerenciador de perfis de agentes.
    
    Funcionalidades:
    - CRUD de perfis com versionamento
    - Seleção automática baseada em match_score
    - Persistência em JSON
    - Métricas de performance por perfil
    """
    
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.profiles_file = self.data_dir / "profiles.json"
        self.metrics_file = self.data_dir / "profile_metrics.json"
        
        self._profiles: dict[str, AgentProfile] = {}
        self._metrics: dict[str, dict[str, Any]] = {}
        
        self._load()
    
    def _load(self) -> None:
        """Carrega perfis do disco."""
        # Carregar perfis
        if self.profiles_file.exists():
            try:
                with open(self.profiles_file, encoding='utf-8') as f:
                    data = json.load(f)
                
                for profile_data in data.get('profiles', []):
                    # Converter capabilities de string para enum
                    caps = []
                    for c in profile_data.get('capabilities', []):
                        if isinstance(c, str):
                            try:
                                caps.append(AgentCapability(c))
                            except ValueError:
                                pass
                        elif isinstance(c, AgentCapability):
                            caps.append(c)
                    
                    profile = AgentProfile(
                        agent_id=profile_data['agent_id'],
                        name=profile_data['name'],
                        capabilities=caps,
                        specialties=profile_data.get('specialties', []),
                        model=profile_data.get('model', 'llama3.2:3b'),
                        system_prompt=profile_data.get('system_prompt', ''),
                        metadata=profile_data.get('metadata', {}),
                        created_at=datetime.fromisoformat(profile_data['created_at']) if 'created_at' in profile_data else datetime.now(UTC),
                        updated_at=datetime.fromisoformat(profile_data['updated_at']) if 'updated_at' in profile_data else datetime.now(UTC),
                        success_rate=profile_data.get('success_rate', 0.0),
                        avg_latency_ms=profile_data.get('avg_latency_ms', 0.0),
                        tasks_completed=profile_data.get('tasks_completed', 0),
                    )
                    self._profiles[profile.name] = profile
                
                logger.info(f"Carregados {len(self._profiles)} perfis")
            except Exception as e:
                logger.error(f"Erro ao carregar perfis: {e}")
        
        # Carregar métricas
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, encoding='utf-8') as f:
                    self._metrics = json.load(f)
            except Exception:
                pass
    
    def _save(self) -> None:
        """Salva perfis no disco."""
        try:
            profiles_data = []
            for profile in self._profiles.values():
                profiles_data.append({
                    'agent_id': profile.agent_id,
                    'name': profile.name,
                    'capabilities': [c.value for c in profile.capabilities],
                    'specialties': profile.specialties,
                    'model': profile.model,
                    'system_prompt': profile.system_prompt,
                    'metadata': profile.metadata,
                    'created_at': profile.created_at.isoformat(),
                    'updated_at': profile.updated_at.isoformat(),
                    'success_rate': profile.success_rate,
                    'avg_latency_ms': profile.avg_latency_ms,
                    'tasks_completed': profile.tasks_completed,
                })
            
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump({'profiles': profiles_data}, f, indent=2, ensure_ascii=False)
            
            # Salvar métricas separadamente
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self._metrics, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar perfis: {e}")
    
    def create_or_update(self, spec: AgentProfileSpec) -> AgentProfile:
        """Cria ou atualiza um perfil."""
        # Verificar se já existe
        existing = self._profiles.get(spec.name)
        
        if existing:
            # Atualizar existente
            existing.capabilities = spec.capabilities
            existing.specialties = spec.specialties
            existing.model = spec.model
            existing.system_prompt = spec.system_prompt
            existing.metadata = spec.metadata
            existing.updated_at = datetime.now(UTC)
            existing.parent_profile_id = spec.parent_profile_id or existing.name
            profile = existing
        else:
            # Criar novo
            profile = AgentProfile(
                agent_id=spec.agent_id,
                name=spec.name,
                capabilities=spec.capabilities,
                specialties=spec.specialties,
                model=spec.model,
                system_prompt=spec.system_prompt,
                metadata=spec.metadata,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self._profiles[spec.name] = profile
        
        self._save()
        logger.info(f"Perfil '{spec.name}' {'atualizado' if existing else 'criado'}")
        return profile
    
    def get(self, name: str) -> AgentProfile | None:
        """Retorna perfil por nome."""
        return self._profiles.get(name)
    
    def get_default(self) -> AgentProfile:
        """Retorna perfil padrão (primeiro ou generalista)."""
        if 'Generalista' in self._profiles:
            return self._profiles['Generalista']
        if self._profiles:
            return next(iter(self._profiles.values()))
        # Fallback: criar perfil mínimo
        return AgentProfile(
            agent_id='default',
            name='Generalista',
            capabilities=[
                AgentCapability.TEXT_GENERATION,
                AgentCapability.CODE_GENERATION,
                AgentCapability.RAG_LOCAL,
            ],
            specialties=['programador'],
            model='llama3.2:3b',
        )
    
    def get_by_specialty(self, specialty: str) -> AgentProfile | None:
        """Retorna perfil que tem a especialidade."""
        for profile in self._profiles.values():
            if specialty in profile.specialties:
                return profile
        return None
    
    def list_all(self) -> list[dict[str, Any]]:
        """Lista todos os perfis com metadados."""
        return [
            {
                'name': p.name,
                'capabilities': [c.value for c in p.capabilities],
                'specialties': p.specialties,
                'model': p.model,
                'created_at': p.created_at.isoformat(),
                'updated_at': p.updated_at.isoformat(),
                'metrics': {
                    'success_rate': p.success_rate,
                    'avg_latency_ms': p.avg_latency_ms,
                    'tasks_completed': p.tasks_completed,
                },
            }
            for p in self._profiles.values()
        ]
    
    async def select_best_profile(
        self, 
        task_description: str, 
        context: str | None = None
    ) -> AgentProfile:
        """
        Seleciona o melhor perfil para uma tarefa.
        
        Combina:
        - match_score baseado em capabilities/keywords
        - Performance histórica (success_rate, latency)
        - Contexto adicional
        """
        if not self._profiles:
            return self.get_default()
        
        scored = []
        full_text = f"{task_description} {context or ''}".lower()
        
        for profile in self._profiles.values():
            score = profile.match_score(full_text)
            
            # Bonus por performance histórica
            if profile.tasks_completed > 5:
                score *= (1.0 + profile.success_rate * 0.15)
                # Penalizar latência alta
                if profile.avg_latency_ms > 30000:
                    score *= 0.9
            
            scored.append((score, profile))
        
        # Ordenar por score descendente
        scored.sort(key=lambda x: x[0], reverse=True)
        
        best_profile = scored[0][1]
        logger.debug(f"Perfil selecionado: {best_profile.name} (score: {scored[0][0]:.2f})")
        
        return best_profile
    
    def delete(self, name: str) -> bool:
        """Remove um perfil."""
        if name in self._profiles and name != 'Generalista':
            del self._profiles[name]
            self._save()
            return True
        return False
    
    def clone_profile(self, source_name: str, new_name: str, modifications: dict[str, Any] | None = None) -> AgentProfile | None:
        """Clona um perfil existente com modificações opcionais."""
        source = self._profiles.get(source_name)
        if not source:
            return None
        
        modifications = modifications or {}
        
        spec = AgentProfileSpec(
            agent_id=source.agent_id,
            name=new_name,
            capabilities=modifications.get('capabilities', source.capabilities),
            specialties=modifications.get('specialties', source.specialties),
            model=modifications.get('model', source.model),
            system_prompt=modifications.get('system_prompt', source.system_prompt),
            metadata=modifications.get('metadata', source.metadata),
            parent_profile_id=source.name,
        )
        
        return self.create_or_update(spec)
    
    def export_profile(self, name: str) -> dict[str, Any] | None:
        """Exporta perfil para dict (para backup/compartilhamento)."""
        profile = self._profiles.get(name)
        if not profile:
            return None
        
        return {
            'name': profile.name,
            'capabilities': [c.value for c in profile.capabilities],
            'specialties': profile.specialties,
            'model': profile.model,
            'system_prompt': profile.system_prompt,
            'metadata': profile.metadata,
            'exported_at': datetime.now(UTC).isoformat(),
        }
    
    def import_profile(self, agent_id: str, data: dict[str, Any]) -> AgentProfile:
        """Importa perfil de dict."""
        caps = []
        for c in data.get('capabilities', []):
            try:
                caps.append(AgentCapability(c))
            except ValueError:
                pass
        
        spec = AgentProfileSpec(
            agent_id=agent_id,
            name=data['name'],
            capabilities=caps,
            specialties=data.get('specialties', []),
            model=data.get('model', 'llama3.2:3b'),
            system_prompt=data.get('system_prompt', ''),
            metadata=data.get('metadata', {}),
        )
        
        return self.create_or_update(spec)