import torch 
import torch.nn as nn 
import numpy as np 
import librosa 

EMOTIONS = ['Calm', 'Happy', 'Sad', 'Angry', 'Fearful', 'Disgust', 'Surprised']


class CNN_BiLSTM_Attention(nn.Module):
    def __init__(self, num_classes=7):
        super().__init__()

        def conv_block(in_f, out_f):
            return nn.Sequential(
                nn.Conv2d(in_f, out_f, kernel_size=3, padding=1),
                nn.BatchNorm2d(out_f),
                nn.ReLU(),
                nn.MaxPool2d(2),
                nn.Dropout2d(0.2)
            )

        self.features = nn.Sequential(
            conv_block(3, 32),
            conv_block(32, 64),
            conv_block(64, 128),
            nn.AdaptiveAvgPool2d((4, 4))
        )

        self.bilstm = nn.LSTM(
            2048, 128,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.3
        )

        self.attn = nn.Linear(256, 1)

        self.classifier = nn.Sequential(
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(64, num_classes)
        )

    def forward(self, x):
        batch, segments, channels, frequency, time = x.shape
        x = self.features(x.view(-1, channels, frequency, time))
        x = x.flatten(1).view(batch, segments, -1)
        lstm_out, _ = self.bilstm(x)
        weights = torch.softmax(self.attn(lstm_out), dim=1)
        context = (lstm_out * weights).sum(dim=1)
        return self.classifier(context)


device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

model = CNN_BiLSTM_Attention(num_classes=7).to(device)
model.load_state_dict(torch.load('model/accuracy.pth', map_location=device))
model.eval()

mean = np.load('model/mean.npy')
std = np.load('model/std.npy')


def load_audio(file_path, sr=22050):
    audio, _ = librosa.load(file_path, sr=sr)
    audio, _ = librosa.effects.trim(audio)
    return audio


def normalize_audio(audio, sr=22050, duration=5):
    audio_len = sr * duration

    if len(audio) < audio_len:
        audio = np.pad(audio, (0, audio_len - len(audio)), mode='reflect')
    else:
        audio = audio[:audio_len]

    return audio


def feature_extraction(audio, sr=22050, n_mels=128, hop_length=256):
    audio = np.append(audio[0], audio[1:] - 0.97 * audio[:-1])

    mel = librosa.feature.melspectrogram(
        y=audio,
        sr=sr,
        n_mels=n_mels,
        hop_length=hop_length,
        n_fft=2048
    )

    mel_db = librosa.power_to_db(mel, ref=np.max)
    delta = librosa.feature.delta(mel_db)
    delta2 = librosa.feature.delta(mel_db, order=2)

    return np.stack([mel_db, delta, delta2], axis=-1)


def segment_melspec(X, segment_size=128, hop_size=64):
    batch, channels, freq, time = X.shape
    segments = []

    for start in range(0, time - segment_size + 1, hop_size):
        segments.append(X[:, :, :, start:start + segment_size])

    return torch.stack(segments, dim=1)


def predict_emotion(audio_path):
    audio = load_audio(audio_path)
    audio = normalize_audio(audio)
    features = feature_extraction(audio)
    features = (features - mean) / std
    features = torch.tensor(features).permute(2, 0, 1).float()
    features = features.unsqueeze(0)
    features = segment_melspec(features)
    features = features.to(device)

    with torch.no_grad():
        output = model(features)
        probs = torch.softmax(output, dim=1).squeeze().cpu().detach().numpy()
        prediction = int(probs.argmax())
        confidence = float(probs[prediction]) * 100

    return EMOTIONS[prediction], confidence