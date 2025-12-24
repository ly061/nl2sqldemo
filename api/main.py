import logging
import urllib.parse
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.routes import api_router, DOWNLOADS_DIR

logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate idiomatic operation IDs for OpenAPI client generation."""
    return route.name


app = FastAPI(
    title="测试用例生成 API",
    description="测试用例生成系统的 API 服务",
    version="1.0.0",
    generate_unique_id_function=custom_generate_unique_id,
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router, prefix="/api/v1")

# 注册下载路由（直接使用 /api/download，不需要 /api/v1 前缀）
# 创建一个单独的 router 用于下载，避免路由冲突
download_router = APIRouter()

@download_router.get("/download/{filename:path}")
async def download_file(filename: str):
    """下载生成的 Excel 文件"""
    try:
        # URL 解码文件名（处理中文文件名）
        decoded_filename = urllib.parse.unquote(filename)
        
        # 验证文件名，防止路径遍历攻击
        if ".." in decoded_filename or "/" in decoded_filename or "\\" in decoded_filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # 构建文件路径
        file_path = DOWNLOADS_DIR / decoded_filename
        
        # 检查文件是否存在
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        # 检查文件是否在 downloads 目录内（防止路径遍历）
        try:
            file_path.resolve().relative_to(DOWNLOADS_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # 返回文件
        return FileResponse(
            path=str(file_path),
            filename=decoded_filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{urllib.parse.quote(decoded_filename)}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

app.include_router(download_router, prefix="/api")


@app.get("/")
async def root():
    """根路径"""
    return {"message": "测试用例生成 API 服务", "version": "1.0.0"}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}

