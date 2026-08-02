/**
 * Configuration Loader - Loads and validates kernel configuration
 * 
 * Implements the IKernelConfig interface.
 * Responsible for loading and validating kernel configuration.
 */

import type { IKernelConfig, KernelConfig } from '../interfaces';
import { ConfigurationError } from '../errors';

/**
 * Default configuration values
 */
const DEFAULT_CONFIG: Partial<KernelConfig> = {
  logLevel: 'info'
};

/**
 * ConfigLoader - Concrete implementation of IKernelConfig
 */
export class ConfigLoader implements IKernelConfig {
  private _config: Record<string, unknown>;

  constructor() {
    this._config = { ...DEFAULT_CONFIG };
  }

  /**
   * Load configuration from source
   * In this initial implementation, configuration is passed directly.
   * Future implementations may load from files, environment variables, etc.
   * @param config - Configuration object to load
   */
  async load(config?: Partial<KernelConfig>): Promise<KernelConfig> {
    if (config) {
      this._config = { ...this._config, ...config };
    }
    
    return this._config as KernelConfig;
  }

  /**
   * Validate configuration
   * @param config - Configuration to validate
   * @returns true if configuration is valid
   * @throws ConfigurationError if validation fails
   */
  validate(config: KernelConfig): boolean {
    // nodeId is required
    if (!config.nodeId || typeof config.nodeId !== 'string') {
      throw new ConfigurationError('nodeId is required and must be a string');
    }

    // nodeId must not be empty
    if (config.nodeId.trim().length === 0) {
      throw new ConfigurationError('nodeId cannot be empty');
    }

    // nodeName is optional but must be a string if provided
    if (config.nodeName !== undefined && typeof config.nodeName !== 'string') {
      throw new ConfigurationError('nodeName must be a string if provided');
    }

    // logLevel must be one of the allowed values if provided
    if (config.logLevel !== undefined) {
      const validLevels = ['debug', 'info', 'warn', 'error'];
      if (!validLevels.includes(config.logLevel)) {
        throw new ConfigurationError(
          `logLevel must be one of: ${validLevels.join(', ')}`
        );
      }
    }

    return true;
  }

  /**
   * Get configuration value by key
   * @param key - Configuration key
   * @param defaultValue - Default value if key doesn't exist
   * @returns Configuration value or default
   */
  get<T>(key: string, defaultValue?: T): T | undefined {
    const value = this._config[key];
    return (value !== undefined ? value : defaultValue) as T | undefined;
  }

  /**
   * Set configuration value
   * @param key - Configuration key
   * @param value - Configuration value
   */
  set(key: string, value: unknown): void {
    this._config[key] = value;
  }

  /**
   * Get all configuration
   * @returns Complete configuration object
   */
  getAll(): Readonly<Record<string, unknown>> {
    return { ...this._config };
  }

  /**
   * Clear all configuration (reset to defaults)
   */
  clear(): void {
    this._config = { ...DEFAULT_CONFIG };
  }
}
