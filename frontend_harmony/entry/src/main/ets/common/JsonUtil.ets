/**
 * JSON 解析辅助工具（ArkTS 严格模式不使用 any）。
 * JSON.parse 的结果统一先断言为 Record / Array 类型，
 * 再通过本文件函数按字段取回基础类型；字段缺失或为 null 时返回 null。
 * 说明：as 断言只影响编译期类型，运行时仍保持 JSON 原始值，调用方需按契约处理可空字段。
 */

/** 把任意 Object 值转换为 JSON 对象（Record），非对象或 null 时返回 null。 */
export function jsonObject(value: Object): Record<string, Object> | null {
  if (value === null || value === undefined) {
    return null;
  }
  return value as Record<string, Object>;
}

/** 把任意 Object 值转换为 JSON 数组，非数组或 null 时返回 null。 */
export function jsonArray(value: Object): Array<Object> | null {
  if (value === null || value === undefined) {
    return null;
  }
  return value as Array<Object>;
}

/** 读取字符串字段，字段缺失或为 null 时返回 null。 */
export function jsonString(json: Record<string, Object>, key: string): string | null {
  const value: Object = json[key];
  if (value === null || value === undefined) {
    return null;
  }
  return value as string;
}

/** 读取字符串字段并提供默认值。 */
export function jsonStringDef(json: Record<string, Object>, key: string, def: string): string {
  const value: string | null = jsonString(json, key);
  if (value !== null) {
    return value;
  }
  return def;
}

/** 读取数值字段（number/int），缺失、null 或非有限数时返回 null。 */
export function jsonNumber(json: Record<string, Object>, key: string): number | null {
  const value: Object = json[key];
  if (value === null || value === undefined) {
    return null;
  }
  const num: number = value as number;
  if (Number.isFinite(num)) {
    return num;
  }
  return null;
}

/** 读取数值字段并提供默认值。 */
export function jsonNumberDef(json: Record<string, Object>, key: string, def: number): number {
  const value: number | null = jsonNumber(json, key);
  if (value !== null) {
    return value;
  }
  return def;
}

/** 读取布尔字段，字段缺失或为 null 时返回 null。 */
export function jsonBool(json: Record<string, Object>, key: string): boolean | null {
  const value: Object = json[key];
  if (value === null || value === undefined) {
    return null;
  }
  return value as boolean;
}

/** 读取布尔字段并提供默认值。 */
export function jsonBoolDef(json: Record<string, Object>, key: string, def: boolean): boolean {
  const value: boolean | null = jsonBool(json, key);
  if (value !== null) {
    return value;
  }
  return def;
}
