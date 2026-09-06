/**
 * 首页新闻列表 ViewModel（E4-06~E4-09 配套）。
 * 负责分类拉取、列表分页（1~50 约束）、下拉/按钮刷新与加载更多；
 * 状态字段均为一层属性，由 @State 持有实例以驱动界面刷新。
 */

import { ApiConfig } from '../common/ApiConfig';
import { HttpClient } from '../common/HttpClient';
import { NewsItem, NewsPageData } from '../model/News';

@Observed
export class NewsViewModel {
  /** 固定六类分类（来自 GET /api/categories，服务端保证稳定顺序）。 */
  categories: string[] = [];

  /** 当前选中分类；空字符串表示全部（仅客户端筛选语义，非额外 API 分类）。 */
  selectedCategory: string = '';

  /** 当前新闻列表（不包含 content）。 */
  newsList: NewsItem[] = [];

  /** 当前已加载页码与服务端总数。 */
  page: number = 1;
  total: number = 0;

  /** 是否还有下一页。 */
  hasMore: boolean = false;

  /** 首页数据（分类+第一页）加载中，且列表为空时展示全屏加载态。 */
  loading: boolean = true;

  /** 下拉/按钮刷新中（列表已有数据）。 */
  refreshing: boolean = false;

  /** 加载更多进行中。 */
  loadingMore: boolean = false;

  /** 加载更多失败（底部展示重试）。 */
  moreFailed: boolean = false;

  /** 错误信息；列表为空时展示整页错误，列表有数据时展示顶部提示条。 */
  errorMessage: string = '';

  private client: HttpClient = new HttpClient();

  /** 首次进入：拉取分类后加载第一页。 */
  async loadInitial(): Promise<void> {
    this.loading = true;
    this.errorMessage = '';
    this.moreFailed = false;
    try {
      const cats: string[] = await this.client.getCategories();
      this.categories = cats;
      if (this.selectedCategory.length > 0 && cats.indexOf(this.selectedCategory) < 0) {
        this.selectedCategory = '';
      }
      await this.fetchFirstPage();
    } catch (err) {
      this.errorMessage = `加载失败：${err.message}`;
    } finally {
      this.loading = false;
      this.refreshing = false;
    }
  }

  /** 刷新：重置到第一页（状态正确复位，E4-09）。 */
  async refresh(): Promise<void> {
    if (this.refreshing || this.loading || this.loadingMore) {
      return;
    }
    this.refreshing = true;
    this.errorMessage = '';
    this.moreFailed = false;
    try {
      await this.fetchFirstPage();
    } catch (err) {
      this.errorMessage = `刷新失败：${err.message}`;
    } finally {
      this.refreshing = false;
    }
  }

  /** 切换分类后重新加载第一页。 */
  async switchCategory(category: string): Promise<void> {
    if (this.selectedCategory === category || this.loading) {
      return;
    }
    this.selectedCategory = category;
    this.errorMessage = '';
    this.moreFailed = false;
    try {
      await this.fetchFirstPage();
    } catch (err) {
      this.errorMessage = `加载失败：${err.message}`;
    }
  }

  /** 加载下一页（触底加载，遵守 page/page_size 契约）。 */
  async loadMore(): Promise<void> {
    if (!this.hasMore || this.loadingMore || this.loading || this.refreshing) {
      return;
    }
    this.loadingMore = true;
    this.moreFailed = false;
    try {
      const nextPage: number = this.page + 1;
      const data: NewsPageData = await this.client.getNewsList(nextPage, ApiConfig.defaultPageSize,
        this.selectedCategory);
      const merged: NewsItem[] = this.newsList.concat(data.items);
      this.newsList = merged;
      this.page = data.page;
      this.total = data.total;
      this.hasMore = data.page * data.page_size < data.total;
    } catch (err) {
      this.moreFailed = true;
    } finally {
      this.loadingMore = false;
    }
  }

  /** 拉取第一页并复位列表。 */
  private async fetchFirstPage(): Promise<void> {
    const data: NewsPageData = await this.client.getNewsList(1, ApiConfig.defaultPageSize,
      this.selectedCategory);
    this.newsList = data.items;
    this.page = data.page;
    this.total = data.total;
    this.hasMore = data.page * data.page_size < data.total;
    this.errorMessage = '';
    this.moreFailed = false;
  }
}
