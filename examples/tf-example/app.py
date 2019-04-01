import fret
import tensorflow as tf
import numpy as np

tf.enable_eager_execution()


def load_data(seq_length=100):
    url = ('https://storage.googleapis.com/download.tensorflow.org/'
           'data/shakespeare.txt')
    path_to_file = tf.keras.utils.get_file('shakespeare.txt', url)
    text = open(path_to_file).read()

    vocab = sorted(set(text))
    stoi = {u: i for i, u in enumerate(vocab)}
    itos = list(vocab)

    text_as_int = np.array([stoi[c] for c in text])

    # Create training examples / targets
    char_dataset = tf.data.Dataset.from_tensor_slices(text_as_int)
    sequences = char_dataset.batch(seq_length + 1, drop_remainder=True)

    def split_input_target(chunk):
        input_text = chunk[:-1]
        target_text = chunk[1:]
        return input_text, target_text

    dataset = sequences.map(split_input_target)

    return dataset, stoi, itos


@fret.configurable
class GRU(tf.keras.Model):
    def __init__(self, batch_size, vocab_size, emb_size=128, rnn_size=256):
        super().__init__()
        if tf.test.is_gpu_available():
            rnn = tf.keras.layers.CuDNNGRU
        else:
            import functools
            rnn = functools.partial(
                tf.keras.layers.GRU, recurrent_activation='sigmoid')

        self.emb = tf.keras.layers.Embedding(
            vocab_size, emb_size,
            batch_input_shape=[batch_size, None])
        self.rnn = rnn(
            rnn_size,
            return_sequences=True,
            recurrent_initializer='glorot_uniform',
            stateful=True)
        self.out = tf.keras.layers.Dense(vocab_size)

    def call(self, x):
        return self.out(self.rnn(self.emb(x)))


@fret.command
def check(ws):
    model = ws.build(batch_size=64, vocab_size=52)
    model.build(tf.TensorShape([64, None]))
    print(model.summary())


@fret.command
def train(ws, batch_size=64, n_epochs=5):
    logger = ws.logger('train')

    dataset, _, itos = load_data()
    dataset = dataset \
        .shuffle(train.config.buffer_size) \
        .batch(batch_size, drop_remainder=True)

    model = ws.build(batch_size=batch_size, vocab_size=len(itos))
    model.build(tf.TensorShape([batch_size, None]))
    optimizer = tf.train.AdamOptimizer()

    checkpoint = tf.train.Checkpoint(optimizer=optimizer, model=model)
    manager = tf.train.CheckpointManager(checkpoint, str(ws.snapshot()), None)
    checkpoint.restore(manager.latest_checkpoint)

    for epoch in range(n_epochs):
        model.reset_states()

        for batch_n, (inp, target) in enumerate(dataset):
            with tf.GradientTape() as tape:
                pred = model(inp)
                loss = tf.losses.sparse_softmax_cross_entropy(target, pred)

            grads = tape.gradient(loss, model.trainable_variables)
            optimizer.apply_gradients(zip(grads, model.trainable_variables))

            if batch_n % 50 == 0:
                template = 'epoch: {}, batch: {}, loss: {:.4f}'
                print(template.format(epoch+1, batch_n, loss))

        manager.save()
        logger.info('epoch: %d, loss: %.4f', epoch + 1, loss)

    model.save_weights(str(ws.snapshot('ckpt_%d' % epoch)))


@fret.command
def gen(ws, start_string, num_generate=1000, temperature=1.0):
    _, stoi, itos = load_data()

    model = ws.build(batch_size=1, vocab_size=len(itos))
    model.build(tf.TensorShape([1, None]))

    checkpoint = tf.train.Checkpoint(model=model)
    manager = tf.train.CheckpointManager(checkpoint, str(ws.snapshot()), None)
    checkpoint.restore(manager.latest_checkpoint)

    # Converting our start string to numbers (vectorizing)
    input_eval = [stoi[s] for s in start_string]
    input_eval = tf.expand_dims(input_eval, 0)

    # Empty string to store our results
    text_generated = []

    model.reset_states()

    for _ in range(num_generate):
        predictions = model(input_eval)
        # remove the batch dimension
        predictions = tf.squeeze(predictions, 0)

        predictions = predictions / temperature
        predicted_id = tf.random.categorical(predictions, num_samples=1)
        predicted_id = predicted_id[-1, 0].numpy()

        input_eval = tf.expand_dims([predicted_id], 0)

        text_generated.append(itos[predicted_id])

    return (start_string + ''.join(text_generated))
