/**
 * 空态组件（E4-18）：空响应展示，与错误态区分（空态无重试语义）。
 */

@Component
export struct EmptyView {
  /** 空态主文案。 */
  hint: string = '暂无数据';

  /** 空态补充说明（可选）。 */
  subHint: string = '';

  build() {
    Column({ space: 8 }) {
      Text('○')
        .fontSize(36)
        .fontColor('#C9CDD4')
      Text(this.hint)
        .fontSize(14)
        .fontColor('#8A8F99')
      if (this.subHint.length > 0) {
        Text(this.subHint)
          .fontSize(12)
          .fontColor('#B0B4BC')
      }
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
  }
}
