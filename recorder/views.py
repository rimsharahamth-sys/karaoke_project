import os
import uuid
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from .models import UploadedSong
from django.views.decorators.csrf import csrf_exempt
from pydub import AudioSegment
import cloudinary.uploader
import subprocess

# Optional: Spleeter separation function
def separate_with_spleeter(input_path, output_dir):
    try:
        from spleeter.separator import Separator
    except Exception as e:
        raise RuntimeError('Spleeter not installed: ' + str(e))
    separator = Separator('spleeter:2stems')
    separator.separate_to_file(input_path, output_dir)
    base = os.path.splitext(os.path.basename(input_path))[0]
    accompaniment = os.path.join(output_dir, base, "accompaniment.wav")
    if os.path.exists(accompaniment):
        return accompaniment
    raise RuntimeError('Separation failed')

def index(request):
    songs = UploadedSong.objects.all().order_by('-created_at')
    return render(request, 'recorder/index.html', {'songs': songs})

def prepare_accompaniment(song: UploadedSong):
    if song.accompaniment_file:
        return song.accompaniment_file.path
    if song.is_instrumental:
        song.accompaniment_file.name = song.original_file.name
        song.save()
        return song.accompaniment_file.path
    in_path = song.original_file.path
    out_dir = os.path.join(settings.MEDIA_ROOT, 'songs', 'separated')
    os.makedirs(out_dir, exist_ok=True)
    try:
        accomp_wav = separate_with_spleeter(in_path, out_dir)
        audio = AudioSegment.from_file(accomp_wav)
        temp_path = os.path.join(out_dir, f'accomp_{uuid.uuid4().hex}.mp3')
        audio.export(temp_path, format='mp3')
        song.accompaniment_file.name = os.path.relpath(temp_path, settings.MEDIA_ROOT).replace('\\','/')
        song.save()
        return temp_path
    except Exception as e:
        raise

@csrf_exempt
def upload_recording(request, song_id):
    if request.method != 'POST':
        return HttpResponse(status=405)

    song = get_object_or_404(UploadedSong, id=song_id)

    try:
        accomp_path = prepare_accompaniment(song)
    except Exception as e:
        return JsonResponse({'error': 'Accompaniment preparation failed: '+str(e)}, status=500)

    rec = request.FILES.get('recording')
    if not rec:
        return JsonResponse({'error': 'No recording file'}, status=400)

    # ---------- SAVE TEMP RECORDING ----------
    temp_rec_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'rec_{uuid.uuid4().hex}.webm')
    os.makedirs(os.path.dirname(temp_rec_path), exist_ok=True)
    with open(temp_rec_path, 'wb') as f:
        for chunk in rec.chunks():
            f.write(chunk)

    # ---------- READ USER RECORDING ----------
    try:
        rec_audio = AudioSegment.from_file(temp_rec_path)
    except:
        return JsonResponse({'error': 'Could not read recording'}, status=400)

    accomp_audio = AudioSegment.from_file(accomp_path)

    # Match sample rate + channels
    rec_audio = rec_audio.set_frame_rate(accomp_audio.frame_rate).set_channels(accomp_audio.channels)

    # Trim to equal duration
    accomp_trimmed = accomp_audio[:len(rec_audio)]

    # Vocal gain
    rec_audio = rec_audio.apply_gain(+3)

    # Mix
    mixed = accomp_trimmed.overlay(rec_audio)

    # ---------- EXPORT FINAL AUDIO (MP3) ----------
    final_audio_path = os.path.join(settings.MEDIA_ROOT, 'finals', f'final_{uuid.uuid4().hex}.mp3')
    os.makedirs(os.path.dirname(final_audio_path), exist_ok=True)
    mixed.export(final_audio_path, format="mp3")

    # ---------- CREATE VIDEO (MP4) WITH IMAGE ----------
    if song.lyrics_image:
        bg_img_path = song.lyrics_image.path
    else:
        bg_img_path = os.path.join(settings.BASE_DIR, 'static/default_lyrics_bg.jpg')

    final_video_path = os.path.join(settings.MEDIA_ROOT, 'finals', f'final_{uuid.uuid4().hex}.mp4')
    logo_path = os.path.join(settings.MEDIA_ROOT, "logo/branks3_logo.png")

    cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", bg_img_path,
        "-i", logo_path,
        "-i", final_audio_path,
        "-filter_complex",
        "[1]scale=80:-1[logo];[logo]format=rgba,colorchannelmixer=aa=0.6[logo_alpha];[0][logo_alpha]overlay=20:20",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        final_video_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # ---------- UPLOAD FINAL VIDEO TO CLOUDINARY ----------
    upload_result = cloudinary.uploader.upload(final_video_path, resource_type="video")
    final_url = upload_result['secure_url']

    return JsonResponse({'final_url': final_url})
