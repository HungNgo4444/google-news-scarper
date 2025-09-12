# Requirements

## Functional Requirements

**FR1:** Hệ thống có thể tạo và quản lý categories với danh sách keywords sử dụng logic OR để tìm kiếm tin tức trên Google News, trong codebase newspaper4k-master đã có:

- GoogleNewsSource class: Tích hợp với Google News API
- Filtering options:

  - Country, period (7d, 1m, etc.)
  - Keywords, topics, locations
  - Exclude websites
- URL decoding: Tự động decode Google News URLs về original URLs
- Proxy support: Hỗ trợ proxy cho Google News requests
- GoogleNewsSource class: Tích hợp với Google News API
- Filtering options:

  - Country, period (7d, 1m, etc.)
  - Keywords, topics, locations
  - Exclude websites
- URL decoding: Tự động decode Google News URLs về original URLs
- Proxy support: Hỗ trợ proxy cho Google News requests

**FR2:** Hệ thống tự động crawl Google News dựa trên keywords trong mỗi category và trích xuất dữ liệu sử dụng các hàm của newspaper4k-master:

**FR3:** Hệ thống lưu trữ các bài báo đã crawl vào PostgreSQL database với thông tin category tương ứng

**FR4:** Hệ thống cung cấp scheduling mechanism để chạy crawl jobs theo lịch định kỳ (hourly, daily, etc.)

**FR5:** Hệ thống có thể xử lý và lưu trữ metadata của article (title, content, author, publish_date, source_url, image_url, category), trích xuất dữ liệu sử dụng các hàm của newspaper4k-master:

- TitleExtractor: trích xuất tiêu đề
- AuthorsExtractor: trích xuất tác giả
- ContentExtractor: trích xuất nội dung chính
- ImageExtractor: trích xuất hình ảnh
- MetadataExtractor: trích xuất metadata
- PublishDateExtractor: trích xuất ngày đăng
- và các kiểu extract khác
- Ngoài ra còn có:

  - Multi-threaded downloads: ThreadPoolExecutor trong multiple modules
  - Source building: Parallel download articles từ news websites
  - Configurable threads: Configuration.number_threads
  - Helper function: fetch_news() cho batch processing
  - Thread timeout: Configurable timeout settings
  - CloudScraper: Bypass Cloudflare protection

**FR6:** Hệ thống cung cấp khả năng thêm/sửa/xóa categories và keywords một cách dynamic

**FR7:** Hệ thống có logging mechanism để track crawling activities và errors

## Non-Functional Requirements

**NFR1:** Hệ thống phải tuân thủ rate limiting của Google News để tránh bị block

**NFR2:** Database phải có khả năng handle concurrent writes từ multiple crawl processes

**NFR3:** Scheduling system phải reliable và có khả năng retry khi fail

**NFR4:** Hệ thống phải có khả năng scale để handle multiple categories đồng thời

**NFR5:** Data integrity phải được đảm bảo với proper database constraints và validations
