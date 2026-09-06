/**
 * 客户端标识管理（E4-03）。
 * 使用 UUID v4 生成 X-Client-ID，并持久化到 Preferences；
 * 收藏、收藏列表、摘要反馈与新闻详情（用户状态）请求通过 HttpClient 自动附加该 Header。
 * 生成规则遵循 docs/API.md：X-Client-ID 必须为 UUID v4 标准字符串。
 */

import { preferences } from '@kit.ArkData';
import { util } from '@kit.ArkTS';
import { common } from '@kit.AbilityKit';
import { ApiConfig } from './ApiConfig';

export class ClientIdManager {
  /** 内存缓存：本进程内已确认的客户端标识。 */
  private static cachedId: string | null = null;

  /** 并发保护：同一时刻只执行一次“读取或创建”流程。 */
  private static inflight: Promise<string> | null = null;

  /** 返回当前已缓存的客户端标识；尚未生成过时返回 null（不主动创建）。 */
  static getClientId(): string | null {
    return ClientIdManager.cachedId;
  }

  /** 确保存在并返回持久化的 UUID v4 客户端标识。 */
  static ensureClientId(context: common.UIAbilityContext): Promise<string> {
    if (ClientIdManager.cachedId !== null) {
      return Promise.resolve(ClientIdManager.cachedId);
    }
    if (ClientIdManager.inflight !== null) {
      return ClientIdManager.inflight;
    }
    ClientIdManager.inflight = ClientIdManager.doEnsure(context);
    return ClientIdManager.inflight;
  }

  /** 读取 Preferences 中已保存的标识；不存在则生成 UUID v4 并持久化。 */
  private static async doEnsure(context: common.UIAbilityContext): Promise<string> {
    try {
      const options: preferences.Options = { name: ApiConfig.prefsName };
      const prefs: preferences.Preferences = await preferences.getPreferences(context, options);
      const value: preferences.ValueType = await prefs.get(ApiConfig.clientIdKey, '');
      const stored: string = value as string;
      if (stored.length > 0) {
        ClientIdManager.cachedId = stored;
        return stored;
      }
      const created: string = util.generateRandomUUID();
      await prefs.put(ApiConfig.clientIdKey, created);
      await prefs.flush();
      ClientIdManager.cachedId = created;
      return created;
    } finally {
      ClientIdManager.inflight = null;
    }
  }
}
