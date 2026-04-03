"""
API de Documentos - Upload, Download e Conversão
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import os
import uuid
import aiofiles
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.core.config import settings
from app.models.usuario import Usuario
from app.models.audit_log import AuditLog, AcaoAudit, ModuloAudit
from app.services.documento_service import DocumentoService, get_documento_service

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".odt", ".rtf"}


def validar_extensao(filename: str) -> bool:
    """Valida extensão do arquivo"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@router.get("/")
async def listar_documentos(
    current_user: Usuario = Depends(get_current_active_user),
):
    """
    Lista documentos disponíveis no diretório de uploads.
    Retorna {documentos: [...]}
    """
    documentos = []
    upload_dir = settings.UPLOAD_DIR

    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            filepath = os.path.join(upload_dir, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                ext = os.path.splitext(filename)[1].lower()
                documentos.append({
                    "filename": filename,
                    "nome": filename,
                    "tamanho": stat.st_size,
                    "extensao": ext,
                    "data_upload": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

    # Também listar do output dir
    output_dir = settings.OUTPUT_DIR
    if os.path.exists(output_dir):
        for filename in os.listdir(output_dir):
            filepath = os.path.join(output_dir, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                ext = os.path.splitext(filename)[1].lower()
                documentos.append({
                    "filename": filename,
                    "nome": filename,
                    "tamanho": stat.st_size,
                    "extensao": ext,
                    "data_upload": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "tipo": "gerado",
                })

    # Ordenar por data mais recente
    documentos.sort(key=lambda d: d["data_upload"], reverse=True)

    return {"documentos": documentos}


@router.post("/upload")
async def upload_documento(
    request: Request,
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload de documento
    
    Formatos aceitos: PDF, DOCX, DOC, TXT, ODT, RTF
    """
    # Validar extensão
    if not validar_extensao(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato não suportado. Use: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Validar tamanho
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Arquivo muito grande. Máximo: {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB"
        )
    
    # Gerar nome único
    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, unique_name)
    
    # Salvar arquivo
    async with aiofiles.open(filepath, 'wb') as f:
        await f.write(content)
    
    # Log
    log = AuditLog(
        acao=AcaoAudit.DOC_UPLOAD,
        modulo=ModuloAudit.DOCUMENTO,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Upload: {file.filename}",
        usuario_ip=request.client.host
    )
    db.add(log)
    await db.commit()
    
    return {
        "filename": unique_name,
        "original_name": file.filename,
        "size": len(content),
        "path": filepath
    }


@router.post("/upload-multiplo")
async def upload_multiplos(
    request: Request,
    files: List[UploadFile] = File(...),
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload de múltiplos documentos
    """
    resultados = []
    
    for file in files:
        if not validar_extensao(file.filename):
            resultados.append({
                "filename": file.filename,
                "success": False,
                "error": "Formato não suportado"
            })
            continue
        
        content = await file.read()
        if len(content) > settings.MAX_UPLOAD_SIZE:
            resultados.append({
                "filename": file.filename,
                "success": False,
                "error": "Arquivo muito grande"
            })
            continue
        
        ext = os.path.splitext(file.filename)[1]
        unique_name = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join(settings.UPLOAD_DIR, unique_name)
        
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(content)
        
        resultados.append({
            "filename": unique_name,
            "original_name": file.filename,
            "success": True,
            "size": len(content)
        })
    
    return {"resultados": resultados}


@router.get("/download/{filename}")
async def download_documento(
    filename: str,
    request: Request,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download de documento
    """
    # Verificar nos dois diretórios
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        filepath = os.path.join(settings.OUTPUT_DIR, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo não encontrado"
        )
    
    # Log
    log = AuditLog(
        acao=AcaoAudit.DOC_DOWNLOAD,
        modulo=ModuloAudit.DOCUMENTO,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Download: {filename}",
        usuario_ip=request.client.host
    )
    db.add(log)
    await db.commit()
    
    return FileResponse(filepath, filename=filename)


@router.post("/converter")
async def converter_documento(
    request: Request,
    filename: str,
    formato_saida: str,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    doc_service: DocumentoService = Depends(get_documento_service)
):
    """
    Converte documento para outro formato
    
    - PDF → TXT (extração de texto)
    - DOCX → PDF
    - TXT → DOCX
    """
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo não encontrado"
        )
    
    try:
        output_path = await doc_service.converter(filepath, formato_saida)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na conversão: {str(e)}"
        )
    
    # Log
    log = AuditLog(
        acao=AcaoAudit.DOC_CONVERTER,
        modulo=ModuloAudit.DOCUMENTO,
        usuario_id=current_user.id,
        usuario_email=current_user.email,
        descricao=f"Conversão: {filename} → {formato_saida}",
        usuario_ip=request.client.host
    )
    db.add(log)
    await db.commit()
    
    return {
        "original": filename,
        "convertido": os.path.basename(output_path),
        "formato": formato_saida
    }


@router.post("/extrair-texto")
async def extrair_texto(
    request: Request,
    filename: str,
    current_user: Usuario = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    doc_service: DocumentoService = Depends(get_documento_service)
):
    """
    Extrai texto de documento PDF ou DOCX
    """
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo não encontrado"
        )
    
    try:
        texto = await doc_service.extrair_texto(filepath)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na extração: {str(e)}"
        )
    
    return {
        "filename": filename,
        "texto": texto,
        "caracteres": len(texto)
    }


@router.delete("/{filename}")
async def deletar_documento(
    filename: str,
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Deleta documento
    """
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        filepath = os.path.join(settings.OUTPUT_DIR, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo não encontrado"
        )
    
    os.remove(filepath)
    
    return {"message": "Arquivo deletado com sucesso"}
