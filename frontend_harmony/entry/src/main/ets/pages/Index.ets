/**
 * 应用入口页：装载主导航框架 MainPage（E4-05）。
 */

import { MainPage } from './MainPage';

@Entry
@Component
struct Index {
  build() {
    Column() {
      MainPage()
        .width('100%')
        .height('100%')
    }
    .width('100%')
    .height('100%')
  }
}
