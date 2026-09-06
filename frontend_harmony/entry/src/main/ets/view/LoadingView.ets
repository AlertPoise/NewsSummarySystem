/**
 * 加载态组件（E4-17）：请求进行中展示，可独立用于各页面。
 */

@Component
export struct LoadingView {
  /** 加载提示文案。 */
  hint: string = '加载中…';

  build() {
    Column({ space: 12 }) {
      LoadingProgress()
        .width(52)
        .height(52)
        .color('#2B6BFF')
      Text(this.hint)
        .fontSize(14)
        .fontColor('#8A8F99')
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
  }
}
