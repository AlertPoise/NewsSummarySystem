/**
 * 错误态组件（E4-19）：展示可理解错误信息并提供重试入口。
 */

@Component
export struct ErrorView {
  /** 错误信息（展示给用户的可理解文案）。 */
  message: string = '加载失败，请稍后重试';

  /** 重试按钮文案。 */
  retryLabel: string = '重试';

  /** 重试回调。 */
  onRetry: () => void = () => {
  };

  build() {
    Column({ space: 14 }) {
      Text('!')
        .fontSize(22)
        .fontColor('#FFFFFF')
        .textAlign(TextAlign.Center)
        .width(44)
        .height(44)
        .borderRadius(22)
        .backgroundColor('#E5484D')
      Text(this.message)
        .fontSize(14)
        .fontColor('#5A5F6A')
        .textAlign(TextAlign.Center)
        .margin({ left: 24, right: 24 })
      Row() {
        Text(this.retryLabel)
          .fontSize(14)
          .fontColor(Color.White)
      }
      .width(96)
      .height(34)
      .borderRadius(17)
      .backgroundColor('#2B6BFF')
      .justifyContent(FlexAlign.Center)
      .onClick(() => {
        this.onRetry();
      })
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
  }
}
