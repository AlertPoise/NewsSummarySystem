/**
 * 页面展示格式化工具：时间与摘要状态的文案转换。
 */

/** 把 ISO 8601 时间字符串格式化为 “yyyy-MM-dd HH:mm:ss”；空值返回空字符串。 */
export function formatIsoTime(iso: string | null): string {
  if (iso === null || iso.length === 0) {
    return '';
  }
  const text: string = iso.replace('T', ' ');
  if (text.length > 19) {
    return text.substring(0, 19);
  }
  return text;
}

/** 摘要状态文案（状态机取值见 DATABASE：pending/processing/completed/failed）。 */
export function summaryStatusLabel(status: string): string {
  if (status === 'completed') {
    return '已生成';
  }
  if (status === 'processing') {
    return '生成中';
  }
  if (status === 'failed') {
    return '生成失败';
  }
  if (status === 'pending') {
    return '待生成';
  }
  return status;
}

/** 摘要状态展示颜色。 */
export function summaryStatusColor(status: string): string {
  if (status === 'completed') {
    return '#2BA471';
  }
  if (status === 'processing') {
    return '#2B6BFF';
  }
  if (status === 'failed') {
    return '#E5484D';
  }
  return '#8A8F99';
}

/** 新闻分类展示颜色（六类固定分类：科技、财经、社会、体育、国内、国际）。 */
export function categoryColor(category: string): string {
  if (category === '科技') {
    return '#2B6BFF';
  }
  if (category === '财经') {
    return '#C07A00';
  }
  if (category === '社会') {
    return '#B5562B';
  }
  if (category === '体育') {
    return '#2BA471';
  }
  if (category === '国内') {
    return '#7A5AF8';
  }
  if (category === '国际') {
    return '#0E8F8F';
  }
  return '#5A5F6A';
}
