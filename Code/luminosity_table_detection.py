import cv2
import numpy as np
from PIL import Image, ImageDraw
import os

def calculate_luminosity(image):
    """Convert image to RGB and calculate luminosity."""
    image = image.convert('RGB')
    pixels = np.array(image)
    luminosity = 0.299 * pixels[:, :, 0] + 0.587 * pixels[:, :, 1] + 0.114 * pixels[:, :, 2]
    return luminosity

def find_peaks(axis, luminosity, pointgap):
    """Find peaks in luminosity (darkest parts)."""
    avg_luminosity = np.mean(luminosity, axis=axis)
    peaks = []
    for i in range(1, len(avg_luminosity) - 1):
        in_range = True
        for offset in range(1, int(pointgap)):
            if not (avg_luminosity[i] < avg_luminosity[int(i - offset)] and avg_luminosity[i] < avg_luminosity[int(i + offset)]):
                in_range = False
                break
        if in_range:
            peaks.append(i)
    return peaks

def find_troughs(axis, luminosity, pointgap):
    """Find troughs in luminosity (lightest parts)."""
    avg_luminosity = np.mean(luminosity, axis=axis)
    troughs = []
    for i in range(1, len(avg_luminosity) - 1):
        in_range = True
        for offset in range(1, int(pointgap)):
            if not (avg_luminosity[i] > avg_luminosity[int(i - offset)] and avg_luminosity[i] > avg_luminosity[int(i + offset)]):
                in_range = False
                break
        if in_range:
            troughs.append(i)
    return troughs

def draw_lines_in_trough_middle(image, troughs, orientation='horizontal'):
    """Draw lines in the middle of the lightest troughs."""
    draw = ImageDraw.Draw(image)
    width, height = image.size

    if orientation == 'horizontal':
        for i in range(len(troughs) - 1):
            mid_trough = (troughs[i] + troughs[i + 1]) // 2
            draw.line([(0, mid_trough), (width, mid_trough)], fill='red', width=1)
    else:
        for i in range(len(troughs) - 1):
            mid_trough = (troughs[i] + troughs[i + 1]) // 2
            draw.line([(mid_trough, 0), (mid_trough, height)], fill='blue', width=1)

    return image

def split_image_with_lines(image_path, lines, temp_dir="temp"):
    """
    Split the image into cells based on detected lines, save them as separate images, and return bounding box coordinates.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load image {image_path}")
        return []

    height, width = img.shape[:2]
    horizontal_lines = sorted(set(line[1] for line in lines if line[1] == line[3]))
    vertical_lines = sorted(set(line[0] for line in lines if line[0] == line[2]))

    # Ensure edges are included
    if not horizontal_lines or horizontal_lines[0] != 0:
        horizontal_lines.insert(0, 0)
    if not horizontal_lines or horizontal_lines[-1] != height:
        horizontal_lines.append(height)
    if not vertical_lines or vertical_lines[0] != 0:
        vertical_lines.insert(0, 0)
    if not vertical_lines or vertical_lines[-1] != width:
        vertical_lines.append(width)

    cells = []
    base_filename = os.path.basename(image_path).rsplit('.', 1)[0]  # Remove the file extension
    
    # Ensure the temporary directory exists
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    min_size = 5  # Minimum size of a cell in pixels

    for i in range(len(horizontal_lines) - 1):
        for j in range(len(vertical_lines) - 1):
            # Bounding box coordinates
            y1, y2 = horizontal_lines[i], horizontal_lines[i + 1]
            x1, x2 = vertical_lines[j], vertical_lines[j + 1]

            # Ensure coordinates are within the image bounds
            if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
                print(f"Skipping invalid crop region for coordinates: ({x1}, {y1}, {x2}, {y2})")
                continue

            # Ensure cells are not too small
            if (x2 - x1) < min_size or (y2 - y1) < min_size:
                print(f"Skipping too small crop region: ({x1}, {y1}, {x2}, {y2})")
                continue

            # Extract cell image
            cell_img = img[y1:y2, x1:x2]

            # Save the image
            cell_img_path = os.path.join(temp_dir, f"{base_filename}_cell_{i}_{j}.png")
            if not cv2.imwrite(cell_img_path, cell_img):
                print(f"Error saving {cell_img_path}")
                continue

            # Save the bounding box coordinates
            cells.append(((x1, y1), (x2, y2)))  # Add bounding box coordinates to list

    return cells  # Returns the list of bounding box coordinates

def find_table_peaks_troughs(image_path, horizontal_state="border", vertical_state="border", horizontal_gap_ratio=17/2077, vertical_gap_ratio=80/1474):
    """Detect table using peaks and troughs in the luminosity."""
    image = Image.open(image_path)
    width, height = image.size
    luminosity = calculate_luminosity(image)

    horizontal_gap = max(1, round(height * horizontal_gap_ratio))
    vertical_gap = max(1, round(width * vertical_gap_ratio))

    horizontal_troughs = find_troughs(1, luminosity, horizontal_gap) if horizontal_state == "border" else find_peaks(1, luminosity, horizontal_gap)
    horizontal_troughs = [int(y) for y in horizontal_troughs if 0 <= y < height]

    vertical_troughs = find_troughs(0, luminosity, vertical_gap) if vertical_state == "border" else find_peaks(0, luminosity, vertical_gap)
    vertical_troughs = [int(x) for x in vertical_troughs if 0 <= x < width]

    if not horizontal_troughs and not vertical_troughs:
        print(f"No table lines detected for {image_path}.")
        return [], [], None

    draw = ImageDraw.Draw(image)
    for i in range(len(horizontal_troughs) - 1):
        mid_trough = (horizontal_troughs[i] + horizontal_troughs[i + 1]) // 2
        draw.line([(0, mid_trough), (width, mid_trough)], fill='red', width=1)

    for i in range(len(vertical_troughs) - 1):
        mid_trough = (vertical_troughs[i] + vertical_troughs[i + 1]) // 2
        draw.line([(mid_trough, 0), (mid_trough, height)], fill='blue', width=1)

    if len(horizontal_troughs) == 1:
        draw.line([(0, horizontal_troughs[0]), (width, horizontal_troughs[0])], fill='red', width=1)

    if len(vertical_troughs) == 1:
        draw.line([(vertical_troughs[0], 0), (vertical_troughs[0], height)], fill='blue', width=1)

    return horizontal_troughs, vertical_troughs, image

def find_table_transitions(image_path, threshold=15, min_distance=10, smoothing_window=5):
    """Detect table transitions based on gradient changes."""
    image = Image.open(image_path).convert('L')
    luminosity = np.array(image)

    def smooth_data(data, window_size):
        return np.convolve(data, np.ones(window_size) / window_size, mode='same')

    def find_transitions(axis, luminosity, threshold, min_distance, window_size):
        avg_luminosity = np.mean(luminosity, axis=axis)
        avg_luminosity = smooth_data(avg_luminosity, window_size)
        gradient = np.diff(avg_luminosity)
        transitions = np.where(np.abs(gradient) > threshold)[0]
        transitions += 1
        filtered_positions = filter_close_positions(transitions.tolist(), min_distance)
        return filtered_positions

    def filter_close_positions(positions, min_distance):
        filtered = [positions[0]] if positions else []
        for pos in positions[1:]:
            if pos - filtered[-1] >= min_distance:
                filtered.append(pos)
        return filtered

    horizontal_transitions = find_transitions(1, luminosity, threshold, min_distance, smoothing_window)
    vertical_transitions = find_transitions(0, luminosity, threshold, min_distance, smoothing_window)

    if not horizontal_transitions and not vertical_transitions:
        print(f"No table transitions detected for {image_path}.")
        return [], [], None

    image_with_lines = draw_lines_in_trough_middle(image.copy(), horizontal_transitions, orientation='horizontal')
    image_with_lines = draw_lines_in_trough_middle(image_with_lines, vertical_transitions, orientation='vertical')

    return horizontal_transitions, vertical_transitions, image_with_lines

def convert_to_pairs(lst):
    """Convert a list of values to consecutive pairs."""
    return [[lst[i], lst[i + 1]] for i in range(len(lst) - 1)]
