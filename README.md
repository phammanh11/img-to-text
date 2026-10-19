# img-to-text

> Công cụ nhận diện ký tự quang học (OCR) và chuyển đổi hình ảnh / câu hỏi trắc nghiệm thành văn bản siêu tốc sử dụng Google Lens API & FastAPI.

## ✨ Tính năng chính
- ⚡ **Nhận diện siêu tốc**: Tích hợp Google Lens OCR cho độ chính xác cao đối với văn bản tiếng Việt và công thức.
- 🎯 **Tự động định dạng câu hỏi**: Làm sạch thanh trạng thái, pin, đồng hồ từ ảnh chụp màn hình; phân tách câu hỏi và các đáp án A, B, C, D rõ ràng.
- 📋 **Sao chép một chạm**: Tự động copy nội dung sạch vào clipboard để tiện tra cứu hoặc dán tài liệu.
- 🌓 **Giao diện hiện đại**: Hỗ trợ Dark Mode, kéo thả ảnh trực tiếp, phím tắt tiện lợi (Ctrl+V để dán ảnh).

## 🚀 Hướng dẫn cài đặt & khởi chạy

1. **Cài đặt thư viện phụ thuộc:**
   ```bash
   pip install fastapi uvicorn pillow pydantic chrome-lens-py
   ```

2. **Chạy ứng dụng:**
   - Cách 1: Chạy file `start.bat` (trên Windows).
   - Cách 2: Chạy lệnh:
     ```bash
     python app.py
     ```

3. **Truy cập ứng dụng:**
   Mở trình duyệt và truy cập `http://localhost:8000`.
